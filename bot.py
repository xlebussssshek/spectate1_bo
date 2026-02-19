import asyncio
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import UserStatusOnline, UserStatusOffline, UpdateUserTyping, UpdateReadHistoryOutbox
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

load_dotenv()

# ================== НАСТРОЙКИ ==================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_ID"))

# Telegram ID целей (теперь указываем ID, а не username)
TARGET_IDS = []

target1 = os.getenv("TARGET1")
if target1:
    TARGET_IDS.append(int(target1))

target2 = os.getenv("TARGET2")
if target2:
    TARGET_IDS.append(int(target2))

target3 = os.getenv("TARGET3")
if target3:
    TARGET_IDS.append(int(target3))

target4 = os.getenv("TARGET4")
if target4:
    TARGET_IDS.append(int(target4))

target5 = os.getenv("TARGET5")
if target5:
    TARGET_IDS.append(int(target5))

SESSION_NAME = "monitor_session"

# ================== КЛИЕНТЫ ==================
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

tracked_users = {}
user_names = {}          
user_notifications = {}       
notifications_enabled = True  
last_typing = {}         
last_read = {}           
last_message_sent = {}   

TYPING_COOLDOWN = 30
READ_COOLDOWN = 5


def now():
    return datetime.now().strftime("%H:%M:%S")

def get_main_keyboard():
    """Главная клавиатура"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Управление уведомлениями")],
            [KeyboardButton(text="Общий статус")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_users_inline_keyboard():
    """Инлайн клавиатура со списком людей"""
    builder = InlineKeyboardBuilder()
    
    for user_id, name in user_names.items():
        status = "(вкл)" if user_notifications.get(user_id, True) else "(выкл)"
        builder.button(
            text=f"{status} {name} (ID: {user_id})",
            callback_data=f"toggle_{user_id}"
        )
    
    builder.button(text="Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

async def notify(text: str):
    """Отправка уведомления только если включено"""
    if notifications_enabled:
        try:
            await bot.send_message(ADMIN_CHAT_ID, text)
        except Exception as e:
            print(f"Ошибка отправки: {e}")

# ================== КОМАНДЫ БОТА ==================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    
    text = "Бот мониторинга (проверка по Telegram ID)\n\n"
    text += "Отслеживается 5 пользователей:\n"
    
    for user_id, name in user_names.items():
        status = "(вкл)" if user_notifications.get(user_id, True) else "(выкл)"
        text += f"- {status} {name} (ID: {user_id})\n"
    
    text += "\nУправление через кнопки"
    
    await message.answer(text, reply_markup=get_main_keyboard())

@dp.message(lambda message: message.text == "Управление уведомлениями")
async def manage_notifications(message: types.Message):
    if not user_names:
        await message.answer("Список людей пуст")
        return
    
    await message.answer(
        "Управление уведомлениями\n\n"
        "Нажми на человека чтобы включить/выключить:",
        reply_markup=get_users_inline_keyboard()
    )

@dp.message(lambda message: message.text == "Общий статус")
async def show_status(message: types.Message):
    text = "Общий статус\n\n"
    
    for user_id, name in user_names.items():
        status = "вкл" if user_notifications.get(user_id, True) else "выкл"
        text += f"- {name} (ID: {user_id}): {status}\n"
    
    await message.answer(text, reply_markup=get_main_keyboard())

@dp.message(Command("check_ids"))
async def check_ids(message: types.Message):
    """Проверка всех ID"""
    text = "Проверка Telegram ID:\n\n"
    
    for user_id in TARGET_IDS:
        if user_id in tracked_users:
            name = tracked_users[user_id].first_name
            text += f"{name} - ID: {user_id}\n"
        else:
            text += f"ID {user_id} - не найден\n"
    
    await message.answer(text)

@dp.message(Command("check_user"))
async def check_user(message: types.Message):
    """Проверка конкретного пользователя по username или ID"""
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /check_user username или /check_user 123456789")
        return
    
    query = args[1]
    
    try:
        if query.isdigit():
            entity = await client.get_entity(int(query))
        else:
            entity = await client.get_entity(query)
        
        user_id = entity.id
        name = entity.first_name if hasattr(entity, 'first_name') else entity.title
        
        text = f"Найден пользователь:\n"
        text += f"Имя: {name}\n"
        text += f"ID: {user_id}\n"
        text += f"Username: @{entity.username}" if hasattr(entity, 'username') and entity.username else "Username: нет"
        
        await message.answer(text)
        
    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}")

@dp.callback_query(lambda c: c.data.startswith("toggle_"))
async def toggle_user(callback: types.CallbackQuery):
    user_id = int(callback.data.replace("toggle_", ""))
    
    current = user_notifications.get(user_id, True)
    user_notifications[user_id] = not current
    
    name = user_names.get(user_id, "Неизвестно")
    status = "включены" if user_notifications[user_id] else "выключены"
    
    await callback.answer(f"Уведомления для {name} (ID: {user_id}) {status}")
    
    await callback.message.edit_reply_markup(reply_markup=get_users_inline_keyboard())

@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Главное меню:", reply_markup=get_main_keyboard())

# ================== ЗАГРУЗКА ЦЕЛЕЙ ==================
async def setup_tracking():
    await client.start()
    me = await client.get_me()
    print(f"Монитор-аккаунт: {me.first_name} (ID: {me.id})")
    
    print(f"\nЗагружаю пользователей по Telegram ID...")
    
    for target_id in TARGET_IDS:
        if not target_id:
            continue
        try:
            entity = await client.get_entity(target_id)
            
            if hasattr(entity, 'first_name'):
                user_id = entity.id
                name = entity.first_name
                username = f" (@{entity.username})" if hasattr(entity, 'username') and entity.username else ""
                
                tracked_users[user_id] = entity
                user_names[user_id] = name
                user_notifications[user_id] = True 
                last_typing[user_id] = datetime.min
                last_read[user_id] = datetime.min
                
                print(f"Загружен: {name}{username}")
                print(f"  ID: {user_id}")
            else:
                print(f"ID {target_id} - не является пользователем (это чат или канал)")
                
        except ValueError as e:
            print(f"Ошибка: ID {target_id} не найден в Telegram")
        except Exception as e:
            print(f"Ошибка загрузки ID {target_id}: {e}")
    
    print(f"\nВсего загружено: {len(tracked_users)} пользователей")

# ================== ОТПРАВЛЕННЫЕ СООБЩЕНИЯ ==================
@client.on(events.NewMessage(outgoing=True))
async def outgoing_message_handler(event):
    """Запоминаем последнее отправленное сообщение цели"""
    message = event.message
    if message.peer_id and hasattr(message.peer_id, 'user_id'):
        user_id = message.peer_id.user_id
        if user_id in tracked_users:
            last_message_sent[user_id] = message.id
            

# ================== ПРОЧТЕНИЕ СООБЩЕНИЙ ==================
@client.on(events.Raw)
async def read_handler(event):
    """Когда наши сообщения прочитаны"""
    if isinstance(event, UpdateReadHistoryOutbox):
        user_id = event.peer.user_id if hasattr(event.peer, 'user_id') else None
        
        if user_id in tracked_users and last_message_sent.get(user_id):
            if event.max_id and event.max_id >= last_message_sent[user_id]:
                last = last_read[user_id]
                if (datetime.now() - last).total_seconds() >= READ_COOLDOWN:
                    last_read[user_id] = datetime.now()
                    name = tracked_users[user_id].first_name
                    await notify(f"Пользователь {name} прочитал сообщение\n{now()}")

# ================== ONLINE/OFFLINE ==================
@client.on(events.UserUpdate)
async def status_handler(event):
    """Изменение статуса онлайн/оффлайн"""
    if event.user_id in tracked_users:
        name = tracked_users[event.user_id].first_name

        if isinstance(event.status, UserStatusOnline):
            await notify(f"{name} зашел в сеть\n{now()}")

        elif isinstance(event.status, UserStatusOffline):
            await notify(f"{name} вышел из сети\n{now()}")

# ================== ПЕЧАТАЕТ ==================
@client.on(events.Raw)
async def typing_handler(event):
    """Когда пользователь печатает"""
    if isinstance(event, UpdateUserTyping):
        user_id = event.user_id
        if user_id in tracked_users:
            last = last_typing[user_id]
            if (datetime.now() - last).total_seconds() >= TYPING_COOLDOWN:
                last_typing[user_id] = datetime.now()
                name = tracked_users[user_id].first_name
                await notify(f"{name} печатает...\n{now()}")

# ================== MAIN ==================
async def main():
    await setup_tracking()
    
    if not tracked_users:
        print("\nВНИМАНИЕ: Не удалось загрузить ни одного пользователя!")
        print("Проверьте правильность Telegram ID в файле .env")
        print("\nКак получить ID пользователя:")
        print("1. Напишите боту @userinfobot")
        print("2. Перешлите ему сообщение от нужного пользователя")
        print("3. Бот покажет его ID")
    
    print("\nМониторинг запущен")
    print("Отслеживается: онлайн, печатает, прочтение сообщений")
    print("Управление через кнопки в боте\n")
    
    status_text = "<b>Мониторинг запущен!</b>\n\n"
    status_text += "Отслеживаемые пользователи:\n"
    for user_id, name in user_names.items():
        status_text += f"• {name} (ID: {user_id})\n"
    status_text += "\nИспользуй кнопки для управления:"
    
    await bot.send_message(
        ADMIN_CHAT_ID, 
        status_text,
        reply_markup=get_main_keyboard()
    )
    
    await asyncio.gather(
        client.run_until_disconnected(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())