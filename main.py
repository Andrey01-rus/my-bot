import os
import json
import random
import logging
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

# --- Константы ---
AI_CHAT = 1

# --- Загрузка данных ---
with open('ideas.json', 'r', encoding='utf-8') as f:
    ideas = json.load(f)

# --- Конфигурация ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1:free"

# --- Клавиатуры ---
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Идея", callback_data='idea'),
         InlineKeyboardButton("📍 Место", callback_data='place')],
        [InlineKeyboardButton("🕹 Игра", callback_data='game'),
         InlineKeyboardButton("🤖 ИИ-чат", callback_data='ai_chat')]
    ])

def ai_chat_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Выйти из ИИ-чата", callback_data='exit_ai')]
    ])

# --- Основные функции ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Добро пожаловать! Я бот с функциями:\n"
        "- Генератор идей\n- Поиск мест\n- Мини-игры\n"
        "- Умный ИИ-чат",
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
    
    return ConversationHandler.END

async def ai_chat_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    """Функция ИИ-чата"""
    if not OPENROUTER_KEY:
        return "⚠️ ИИ-чат недоступен (не настроен API-ключ)"
    
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

    logger.info("Бот успешно запущен (без мемов)")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
