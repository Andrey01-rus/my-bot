import os
import json
import random
import logging
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatAction
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

# --- Константы ---
AI_CHAT = 1
IMGUR_API_URL = "https://api.imgur.com/3/gallery/search/top/week?q=meme"
DEFAULT_MEMES = [
    "https://i.imgur.com/8J7nD7B.jpg",
    "https://i.imgur.com/5Z4w1Qq.jpg",
    "https://i.imgur.com/3JQ2X9Y.jpg"
]

# --- Глобальные переменные ---
MEME_CACHE = []
LAST_CACHE_UPDATE = None

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
async def update_meme_cache():
    """Обновление кеша мемов"""
    global MEME_CACHE, LAST_CACHE_UPDATE
    try:
        headers = {'Authorization': 'Client-ID 546c25a59c58ad7'}
        response = requests.get(IMGUR_API_URL, headers=headers, timeout=10)
        response.raise_for_status()
        
        MEME_CACHE = []
        for item in response.json()['data']:
            if 'images' in item and not item.get('nsfw', True):
                for image in item['images']:
                    if image['type'].startswith('image/'):
                        MEME_CACHE.append({
                            "url": image['link'],
                            "source": f"https://imgur.com/gallery/{item['id']}",
                            "title": item['title'] if 'title' in item else "Мем с Imgur"
                        })
        LAST_CACHE_UPDATE = datetime.now()
        return MEME_CACHE[:50]
    except Exception as e:
        logger.error(f"Ошибка Imgur API: {e}")
        return []

async def get_fresh_memes():
    """Получение свежих мемов с кешированием"""
    global MEME_CACHE, LAST_CACHE_UPDATE
    
    if not MEME_CACHE or (datetime.now() - LAST_CACHE_UPDATE).total_seconds() > 3600:
        await update_meme_cache()
    
    return MEME_CACHE or [{
        "url": url,
        "source": "Резервный мем",
        "title": "Классический мем"
    } for url in DEFAULT_MEMES]

async def send_random_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка мема с обработкой ошибок"""
    query = update.callback_query
    try:
        # Немедленное подтверждение callback
        await query.answer()
        
        # Проверка возраста запроса
        if (datetime.now() - query.message.date).total_seconds() > 60:
            await query.edit_message_text("⚠️ Сообщение устарело. Нажмите кнопку снова.")
            return

        # Уведомление о начале загрузки
        await context.bot.send_chat_action(
            chat_id=query.message.chat_id, 
            action=ChatAction.UPLOAD_PHOTO
        )
        
        memes = await get_fresh_memes()
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
        "- Умный ИИ-чат\n- Свежие мемы",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        # Немедленное подтверждение callback
        await query.answer()
        
        # Проверка возраста запроса
        if (datetime.now() - query.message.date).total_seconds() > 60:
            await query.edit_message_text("⚠️ Сообщение устарело. Нажмите кнопку снова.")
            return ConversationHandler.END

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
    except Exception as e:
        logger.error(f"Ошибка в button_handler: {e}")
        await query.edit_message_text("⚠️ Произошла ошибка. Попробуйте снова.")
        return ConversationHandler.END

async def ai_chat_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Уведомление о начале обработки
        await context.bot.send_chat_action(
            chat_id=update.message.chat_id,
            action=ChatAction.TYPING
        )
        
        answer = await ask_ai(update.message.text)
        await update.message.reply_text(f"🤖 {answer}", reply_markup=ai_chat_keyboard())
    except Exception as e:
        logger.error(f"Ошибка ИИ: {e}")
        await update.message.reply_text("⚠️ Ошибка генерации ответа", reply_markup=ai_chat_keyboard())
    return AI_CHAT

async def exit_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ Вы вышли из ИИ-чата", reply_markup=main_keyboard())
    return ConversationHandler.END

async def ask_ai(prompt):
    """Функция ИИ-чата с обработкой таймаутов"""
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
            timeout=15  # Уменьшенный таймаут
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.Timeout:
        return "Извините, ИИ не ответил вовремя. Попробуйте позже."
    except Exception as e:
        raise Exception(f"Ошибка API: {str(e)[:200]}")

# --- Запуск бота ---
def main():
    application = Application.builder().token(TOKEN).build()

    # Регистрация обработчиков
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

    logger.info("Бот успешно запущен!")
    
    try:
        application.run_polling(
            drop_pending_updates=True,
            poll_interval=0.5,
            timeout=20,
            read_timeout=20,
            connect_timeout=20
        )
    except NetworkError as e:
        logger.error(f"Network error: {e}")
        # Логика переподключения
    except Exception as e:
        logger.error(f"Critical error: {e}")

if __name__ == '__main__':
    main()
