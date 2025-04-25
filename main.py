from flask import Flask
from threading import Thread
import json
import random
import requests
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)
import feedparser
from datetime import datetime

# Инициализация Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Бот активен!"

# Константы
AI_CHAT = 1
MEME_CHANNELS = [
    "https://rsshub.app/telegram/channel/mudakoff",  # Мемы
    "https://rsshub.app/telegram/channel/typical_mem",  # Типичные мемы
    "https://rsshub.app/telegram/channel/mem_s_mestami"  # Мемы с местами
]

# Загрузка идей
with open('ideas.json', 'r', encoding='utf-8') as f:
    ideas = json.load(f)

# Конфигурация бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1:free"

# Клавиатуры
def main_keyboard():
    buttons = [
        [InlineKeyboardButton("🎲 Идея", callback_data='idea'),
         InlineKeyboardButton("📍 Место", callback_data='place')],
        [InlineKeyboardButton("🕹 Игра", callback_data='game'),
         InlineKeyboardButton("🤖 ИИ-чат", callback_data='ai_chat')],
        [InlineKeyboardButton("🖼 Свежие мемы (5 шт)", callback_data='tg_memes')]
    ]
    return InlineKeyboardMarkup(buttons)

def ai_chat_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Выйти из ИИ-чата", callback_data='exit_ai')]
    ])

# ИИ-функционал (ваш оригинальный код)
async def ask_ai(prompt):
    try:
        messages = [
            {"role": "system", "content": "Отвечай кратко и по делу."},
            {"role": "user", "content": prompt}
        ]
        
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
                "messages": messages,
                "temperature": 1.0
            },
            timeout=20
        )

        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return "⚠️ Ошибка, попробуйте позже"

# Получение мемов через RSS
async def get_telegram_memes():
    memes = []
    for channel in MEME_CHANNELS:
        try:
            feed = feedparser.parse(channel)
            for entry in feed.entries[:3]:  # Берем по 3 мема с каждого канала
                if hasattr(entry, 'media_content'):
                    memes.append({
                        'url': entry.media_content[0]['url'],
                        'source': entry.link
                    })
        except Exception as e:
            print(f"Ошибка парсинга {channel}: {e}")
    return memes[:5]  # Возвращаем не более 5 мемов

# Отправка мемов
async def send_telegram_memes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        memes = await get_telegram_memes()
        
        if not memes:
            await query.edit_message_text("😔 Мемы закончились. Попробуйте позже!", reply_markup=main_keyboard())
            return
            
        for meme in memes:
            try:
                await query.message.reply_photo(
                    photo=meme['url'],
                    caption=f"Источник: {meme['source']}"
                )
            except Exception as e:
                print(f"Ошибка отправки мема: {e}")
                
        await query.message.reply_text(
            "Что еще хотите сделать?",
            reply_markup=main_keyboard()
        )
    except Exception as e:
        print(f"Ошибка: {e}")
        await query.edit_message_text("⚠️ Ошибка загрузки мемов", reply_markup=main_keyboard())

# Остальные обработчики (без изменений)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Привет! Я бот с мемами и не только:",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'ai_chat':
        await query.edit_message_text(
            "💬 Режим ИИ-чата. Просто напишите вопрос!",
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

# Настройка ConversationHandler
conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(button_handler, pattern='^ai_chat$')],
    states={
        AI_CHAT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat_mode),
            CallbackQueryHandler(exit_ai_chat, pattern='^exit_ai$')
        ]
    },
    fallbacks=[
        CommandHandler('start', start),
        CallbackQueryHandler(exit_ai_chat, pattern='^exit_ai$')
    ]
)

def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == '__main__':
    # Запускаем Flask в отдельном потоке
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Инициализация бота
    bot_app = Application.builder().token(TOKEN).build()
    
    # Регистрация обработчиков
    bot_app.add_handler(CommandHandler('start', start))
    bot_app.add_handler(conv_handler)
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.add_handler(CallbackQueryHandler(send_telegram_memes, pattern='^tg_memes$'))
    
    print("🤖 Бот запущен!")
    bot_app.run_polling(drop_pending_updates=True)
