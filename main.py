from flask import Flask
from threading import Thread
import json
import random
import requests
import os
from datetime import datetime
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

# --- Инициализация Flask ---
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Бот активен!"

# --- Константы ---
AI_CHAT = 1
REDDIT_SUBREDDITS = ["memes", "dankmemes", "Pikabu"]
MEME_CACHE = {
    "memes": [],
    "last_update": None
}

# --- Загрузка данных ---
with open('ideas.json', 'r', encoding='utf-8') as f:
    ideas = json.load(f)

# --- Конфигурация бота ---
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
    """Получаем свежие мемы с Reddit"""
    global MEME_CACHE
    
    # Проверяем кеш (обновляем раз в 2 часа)
    if MEME_CACHE["last_update"] and (datetime.now() - MEME_CACHE["last_update"]).seconds < 7200:
        return MEME_CACHE["memes"]
    
    new_memes = []
    for subreddit in REDDIT_SUBREDDITS:
        try:
            url = f"https://www.reddit.com/r/{subreddit}/top.json?limit=10&t=day"
            headers = {"User-Agent": "MemeBot/1.0"}
            response = requests.get(url, headers=headers, timeout=15)
            
            for post in response.json().get("data", {}).get("children", []):
                if post["data"].get("post_hint") == "image":
                    new_memes.append({
                        "url": post["data"]["url"],
                        "source": f"https://reddit.com{post['data']['permalink']}",
                        "title": post["data"]["title"]
                    })
        except Exception as e:
            print(f"Ошибка парсинга r/{subreddit}: {e}")
    
    MEME_CACHE = {
        "memes": new_memes[:50],  # Сохраняем 50 свежих мемов
        "last_update": datetime.now()
    }
    return MEME_CACHE["memes"]

async def send_random_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляем случайный мем"""
    query = update.callback_query
    await query.answer()
    
    try:
        memes = await fetch_reddit_memes()
        if not memes:
            await query.edit_message_text("😔 Мемы закончились. Попробуйте позже!", 
                                      reply_markup=main_keyboard())
            return
        
        meme = random.choice(memes)
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=meme["url"],
            caption=f"<b>{meme['title']}</b>\n\nИсточник: {meme['source']}",
            reply_markup=meme_keyboard(),
            parse_mode="HTML"
        )
        await query.message.delete()
    except Exception as e:
        print(f"Ошибка отправки мема: {e}")
        await query.edit_message_text("⚠️ Ошибка загрузки мемов", 
                                    reply_markup=main_keyboard())

# --- Оригинальные функции бота ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Привет! Я бот с функциями:\n"
        "- Генератор идей\n- Поиск мест\n- Игры\n"
        "- ИИ-чат\n- Свежие мемы с Reddit",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'ai_chat':
        await query.edit_message_text(
            "💬 Режим ИИ-чата. Отправьте ваш вопрос:",
            reply_markup=ai_chat_keyboard()
        )
        return AI_CHAT

    if query.data in ['idea', 'place', 'game']:
        category_map = {
            'idea': 'activities',
            'place': 'places',
            'game': 'games'
        }
        response = random.choice(ideas[category_map[query.data]])
        await query.edit_message_text(
            text=f"🎯 {response}",
            reply_markup=main_keyboard()
        )
    
    if query.data == 'back':
        await query.edit_message_text(
            "Главное меню:",
            reply_markup=main_keyboard()
        )
    
    return ConversationHandler.END

async def ai_chat_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = await ask_ai(update.message.text)
    await update.message.reply_text(
        f"🤖 {answer}",
        reply_markup=ai_chat_keyboard()
    )
    return AI_CHAT

async def exit_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✅ Вы вышли из ИИ-чата",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

# --- ИИ-функционал ---
async def ask_ai(prompt):
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
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=20
        )
        
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return "⚠️ Ошибка генерации ответа"

# --- Запуск приложения ---
def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == '__main__':
    # Запускаем Flask в отдельном потоке
    Thread(target=run_flask, daemon=True).start()

    # Инициализация бота
    bot_app = Application.builder().token(TOKEN).build()
    
    # Регистрация обработчиков
    bot_app.add_handler(CommandHandler('start', start))
    
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
    
    bot_app.add_handler(conv_handler)
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.add_handler(CallbackQueryHandler(send_random_meme, pattern='^(get_meme|more_memes)$'))
    
    print("🤖 Бот успешно запущен!")
    bot_app.run_polling(drop_pending_updates=True)
