import os
import json
import random
import logging
import socket
import sys
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)

# --- Настройка логов ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Блокировка дублирующихся процессов ---
try:
    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    lock_socket.bind('\0' + 'antiskuka_bot_lock')
except socket.error:
    logger.error("Бот уже запущен! Завершаю процесс.")
    sys.exit(1)

# --- Инициализация Flask ---
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Бот активен!"

# --- Константы ---
AI_CHAT = 1
MEME_SOURCES = [
    # Открытые API мемов
    "https://meme-api.com/gimme",
    # Альтернативные источники
    "https://api.imgflip.com/get_memes",
    # Резервные URL мемов
    "https://i.imgur.com/example1.jpg",
    "https://i.imgur.com/example2.jpg"
]

# --- Загрузка данных ---
try:
    with open('ideas.json', 'r', encoding='utf-8') as f:
        ideas = json.load(f)
except Exception as e:
    logger.error(f"Ошибка загрузки ideas.json: {e}")
    ideas = {
        "activities": ["Идея 1", "Идея 2"],
        "places": ["Место 1", "Место 2"],
        "games": ["Игра 1", "Игра 2"]
    }

# --- Конфигурация ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    logger.error("Токен Telegram не найден!")
    sys.exit(1)

# --- Клавиатуры ---
def main_keyboard():
    buttons = [
        [InlineKeyboardButton("🎲 Идея", callback_data='idea'),
         InlineKeyboardButton("📍 Место", callback_data='place')],
        [InlineKeyboardButton("🕹 Игра", callback_data='game'),
         InlineKeyboardButton("🤖 ИИ-чат", callback_data='ai_chat')],
        [InlineKeyboardButton("🖼 Случайный мем", callback_data='get_meme')]
    ]
    return InlineKeyboardMarkup(buttons)

def ai_chat_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Выйти из ИИ-чата", callback_data='exit_ai')]
    ])

def meme_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Ещё мем", callback_data='more_memes')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back')]
    ])

# --- Функции мемов ---
async def get_random_meme():
    """Получаем мем из случайного источника"""
    try:
        # Пробуем открытые API
        response = requests.get(MEME_SOURCES[0], timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "url": data["url"],
                "source": data["postLink"]
            }
    except Exception as e:
        logger.warning(f"API мемов недоступно: {e}")

    # Если API не сработало, берем из резервных URL
    return {
        "url": random.choice(MEME_SOURCES[2:]),
        "source": "Архив мемов"
    }

async def send_random_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка мема с обработкой ошибок"""
    query = update.callback_query
    await query.answer()
    
    try:
        meme = await get_random_meme()
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=meme["url"],
            caption=f"🔗 {meme['source']}",
            reply_markup=meme_keyboard()
        )
        await query.message.delete()
    except Exception as e:
        logger.error(f"Ошибка отправки мема: {e}")
        await query.edit_message_text(
            "😢 Не удалось загрузить мем. Попробуйте позже!",
            reply_markup=main_keyboard()
        )

# --- Основные функции бота ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Добро пожаловать! Я бот с функциями:\n"
        "- Генератор идей\n- Поиск мест\n- Мини-игры\n"
        "- Случайные мемы",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'ai_chat':
        await query.edit_message_text(
            "💬 Режим ИИ-чата временно недоступен",
            reply_markup=main_keyboard()
        )
        return ConversationHandler.END

    if query.data in ['idea', 'place', 'game']:
        response = random.choice(ideas[{
            'idea': 'activities',
            'place': 'places',
            'game': 'games'
        }[query.data]])
        await query.edit_message_text(f"🎯 {response}", reply_markup=main_keyboard())
    
    if query.data == 'back':
        await query.edit_message_text("Главное меню:", reply_markup=main_keyboard())
    
    return ConversationHandler.END

# --- Запуск приложения ---
def run_flask():
    app.run(host='0.0.0.0', port=8080)

def main() -> None:
    """Запуск бота"""
    # Запуск Flask
    Thread(target=run_flask, daemon=True).start()

    # Инициализация бота
    application = Application.builder().token(TOKEN).build()

    # Обработчики
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CallbackQueryHandler(send_random_meme, pattern='^(get_meme|more_memes)$'))

    # Удаляем старые обновления при запуске
    application.drop_pending_updates = True

    # Запуск
    logger.info("🟢 Запускаю бота...")
    application.run_polling()

if __name__ == '__main__':
    main()
    import requests
response = requests.get(url, timeout=10)  # Макс 10 секунд на запрос
