import os
import json
import random
import requests
import socket
import sys
import asyncio
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

# --- Блокировка дублирующихся процессов ---
try:
    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    lock_socket.bind('\0' + 'antiskuka_bot_lock')
except socket.error:
    print("⚠️ Бот уже запущен! Завершаю процесс.")
    sys.exit(1)

# --- Инициализация Flask ---
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Бот активен и работает!"

# --- Константы ---
AI_CHAT = 1
REDDIT_SUBREDDITS = ["memes", "dankmemes", "Pikabu"]
MEME_CACHE = {"memes": [], "last_update": None}

# --- Загрузка данных ---
with open('ideas.json', 'r', encoding='utf-8') as f:
    ideas = json.load(f)

# --- Конфигурация ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1:free"

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
async def fetch_reddit_memes():
    """Получаем мемы с Reddit через официальный API"""
    global MEME_CACHE
    
    if MEME_CACHE["last_update"] and (datetime.now() - MEME_CACHE["last_update"]).seconds < 7200:
        return MEME_CACHE["memes"]
    
    new_memes = []
    for subreddit in REDDIT_SUBREDDITS:
        try:
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=15"
            headers = {"User-Agent": "TelegramBot/1.0"}
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            for post in data["data"]["children"]:
                if post["data"].get("post_hint") == "image":
                    new_memes.append({
                        "url": post["data"]["url"],
                        "source": f"https://reddit.com{post['data']['permalink']}",
                        "title": post["data"]["title"]
                    })
        except Exception as e:
            print(f"Ошибка при получении мемов с r/{subreddit}: {str(e)[:100]}...")
    
    MEME_CACHE = {
        "memes": new_memes[:20],
        "last_update": datetime.now()
    }
    return MEME_CACHE["memes"]

async def send_random_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка мема с обработкой ошибок"""
    query = update.callback_query
    await query.answer()
    
    try:
        memes = await fetch_reddit_memes()
        if not memes:
            raise Exception("Нет доступных мемов")
        
        meme = random.choice(memes)
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=meme["url"],
            caption=f"<b>{meme['title']}</b>\n\n🔗 {meme['source']}",
            reply_markup=meme_keyboard(),
            parse_mode="HTML"
        )
        await query.message.delete()
    except Exception as e:
        print(f"Ошибка при отправке мема: {e}")
        await query.edit_message_text(
            "😢 Не удалось загрузить мем. Попробуйте позже!",
            reply_markup=main_keyboard()
        )

# --- Основные функции бота ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Добро пожаловать! Я бот с функциями:\n"
        "- Генератор идей\n- Поиск мест\n- Мини-игры\n"
        "- Умный ИИ-чат\n- Свежие мемы с Reddit",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'ai_chat':
        await query.edit_message_text(
            "💬 Режим ИИ-чата. Задайте ваш вопрос:",
            reply_markup=ai_chat_keyboard()
        )
        return AI_CHAT

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

async def ai_chat_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        answer = await ask_ai(update.message.text)
        await update.message.reply_text(f"🤖 {answer}", reply_markup=ai_chat_keyboard())
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        await update.message.reply_text("⚠️ Ошибка генерации ответа", reply_markup=ai_chat_keyboard())
    return AI_CHAT

async def exit_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ Вы вышли из ИИ-чата", reply_markup=main_keyboard())
    return ConversationHandler.END

async def ask_ai(prompt):
    """Улучшенный ИИ-чат с обработкой ошибок"""
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "HTTP-Referer": "https://github.com/AntiSkukaBot",
            "X-Title": "AntiSkukaBot AI"
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            },
            timeout=20
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        raise Exception(f"Ошибка API: {str(e)[:200]}")

# --- Запуск приложения ---
def run_flask():
    app.run(host='0.0.0.0', port=8080)

async def post_init(application: Application) -> None:
    """Функция для инициализации"""
    print("✅ Бот успешно инициализирован")

def main() -> None:
    """Запуск бота"""
    # Запуск Flask
    Thread(target=run_flask, daemon=True).start()

    # Инициализация бота
    application = Application.builder().token(TOKEN).post_init(post_init).build()

    # Обработчики
    application.add_handler(CommandHandler('start', start))
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^ai_chat$')],
        states={
            AI_CHAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat_mode),
                CallbackQueryHandler(exit_ai_chat, pattern='^exit_ai$')
            ]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CallbackQueryHandler(send_random_meme, pattern='^(get_meme|more_memes)$'))

    # Запуск
    print("🟢 Запускаю бота с параметрами:")
    print(f"- Модель: {MODEL}")
    print(f"- Сабреддиты: {', '.join(REDDIT_SUBREDDITS)}")
    
    application.run_polling(
        drop_pending_updates=True,
        close_loop=False,
        stop_signals=[]
    )

if __name__ == '__main__':
    main()
