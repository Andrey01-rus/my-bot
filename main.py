import os
import json
import random
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Настройка логов ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Константы ---
IMGUR_API_URL = "https://api.imgur.com/3/gallery/search/top/week?q=meme"
DEFAULT_MEMES = [
    "https://i.imgur.com/8J7nD7B.jpg",
    "https://i.imgur.com/5Z4w1Qq.jpg",
    "https://i.imgur.com/3JQ2X9Y.jpg"
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

# --- Функции мемов ---
def get_imgur_memes():
    """Получаем топ мемов с Imgur без авторизации"""
    try:
        headers = {'Authorization': 'Client-ID 546c25a59c58ad7'}  # Публичный ключ
        response = requests.get(IMGUR_API_URL, headers=headers, timeout=10)
        response.raise_for_status()
        
        memes = []
        for item in response.json()['data']:
            if 'images' in item and not item.get('nsfw', True):
                for image in item['images']:
                    if image['type'].startswith('image/'):
                        memes.append({
                            "url": image['link'],
                            "source": f"https://imgur.com/gallery/{item['id']}"
                        })
        return memes[:50]  # Берем первые 50
    except Exception as e:
        logger.error(f"Ошибка Imgur API: {e}")
        return []

async def send_random_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка случайного мема"""
    try:
        memes = get_imgur_memes() or [{"url": url, "source": "Резервный мем"} for url in DEFAULT_MEMES]
        meme = random.choice(memes)
        
        await update.message.reply_photo(
            photo=meme["url"],
            caption=f"🔗 Источник: {meme['source']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎲 Ещё мем", callback_data='more_memes')],
                [InlineKeyboardButton("🔙 Назад", callback_data='back')]
            ])
        )
    except Exception as e:
        logger.error(f"Ошибка отправки мема: {e}")
        await update.message.reply_text("😢 Не удалось загрузить мем. Попробуйте позже!")

# --- Основные функции бота ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Идея", callback_data='idea')],
        [InlineKeyboardButton("🖼 Случайный мем", callback_data='meme')]
    ])
    await update.message.reply_text("🚀 Выберите действие:", reply_markup=keyboard)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'meme':
        await send_random_meme(update, context)
    elif query.data in ['idea', 'place', 'game']:
        response = random.choice(ideas[query.data])
        await query.edit_message_text(f"🎯 {response}")

# --- Запуск бота ---
def main():
    app = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
