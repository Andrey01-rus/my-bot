from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Бот активен!"

Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
import json
import random
import requests
import os
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

# Константы состояний
AI_CHAT = 1

# Загрузка идей
with open('ideas.json', 'r', encoding='utf-8') as f:
    ideas = json.load(f)

# Конфигурация
TOKEN = os.environ["TOKEN"]
OPENROUTER_KEY = os.environ["OPENROUTER_KEY"]
MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1:free"  # DeepSeek-R1

# Клавиатуры
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

# ИИ-функционал с фильтрацией
async def ask_ai(prompt):
    try:
        messages = [
            {
                "role": "system", 
                "content": "Отвечай сразу без предварительных размышлений. Не используй пометки вроде 'Thought Process' или 'Step-by-Step explanation'."
            },
            {
                "role": "user",
                "content": f"{prompt}\n\nОтвет должен содержать только итоговый результат без объяснений."
            }
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
                "temperature": 1.0  # Максимальная креативность
            },
            timeout=20
        )

        answer = response.json()['choices'][0]['message']['content']

        # Фильтрация ответа
        filters = [
            "**Answer:**",
            "Thought Process:", 
            "Step-by-Step Explanation:",
            "Пошаговое объяснение:"
        ]

        for f in filters:
            if f in answer:
                answer = answer.split(f, 1)[-1].strip()

        return answer.strip('*').strip()

    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return "⚠️ Произошла ошибка, попробуйте задать вопрос иначе"

# Обработчики
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Привет! Я умный бот-помощник:\n"
        "- Генератор идей\n"
        "- Поиск мест\n"
        "- Игры\n"
        "- Продвинутый ИИ-чат",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'ai_chat':
        await query.edit_message_text(
            "💬 Вы в режиме ИИ-чата. Можете:\n"
            "- Задавать сложные вопросы\n"
            "- Просить советы\n"
            "- Генерировать креативные идеи\n\n"
            "Просто напишите ваш запрос!",
            reply_markup=ai_chat_keyboard()
        )
        return AI_CHAT

    try:
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

    except Exception as e:
        await query.edit_message_text("😕 Ошибка, попробуйте другой вариант", reply_markup=main_keyboard())

    return ConversationHandler.END

async def ai_chat_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text
    answer = await ask_ai(prompt)
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
    ],
    map_to_parent={ConversationHandler.END: ConversationHandler.END}
)

# Запуск
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🤖 Бот запущен и готов к работе!")
    app.run_polling()