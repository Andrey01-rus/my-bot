import os
from telegram.ext import Updater

# Добавьте эту проверку перед запуском бота
if os.environ.get('RUNNING_IN_RENDER'):
    # Настройки для Render
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Бот запущен в Render!")
    app.run_polling(
        drop_pending_updates=True,  # Важно: игнорирует старые сообщения при перезапуске
        allowed_updates=Update.ALL_TYPES
    )
else:
    # Локальная конфигурация (если нужно)
    print("⚠️ Запускайте бота только на Render!")from flask import Flask
from threading import Thread
import json
import random
import requests
import os
import vk_api
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

# Flask сервер для проверки активности
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Бот активен!"

Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

# Константы состояний
AI_CHAT = 1

# Загрузка идей
with open('ideas.json', 'r', encoding='utf-8') as f:
    ideas = json.load(f)

# Конфигурация
TOKEN = os.environ["TOKEN"]
OPENROUTER_KEY = os.environ["OPENROUTER_KEY"]
VK_TOKEN = os.environ.get("VK_TOKEN", "")  # Добавляем токен VK
MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1:free"

# Безопасные паблики VK (с разрешением на репост)
SAFE_PUBLICS = [
    -97216585,  # @video
    -34317336,  # @tnt
    -34017843,  # @lentach
    -15755094,  # @oldlentach
    -53827980   # @bratishkinoff
]

class VKParser:
    def __init__(self):
        self.vk = vk_api.VkApi(token=VK_TOKEN)

    def get_safe_content(self, count=5):
        """Возвращает безопасные медиафайлы из VK"""
        result = []
        for public_id in SAFE_PUBLICS:
            try:
                posts = self.vk.method("wall.get", {
                    "owner_id": public_id,
                    "count": 10,
                    "filter": "owner"
                })["items"]
                
                for post in posts:
                    if len(result) >= count:
                        break
                    if "attachments" in post:
                        for attach in post["attachments"]:
                            if attach["type"] == "photo":
                                photo = attach["photo"]
                                url = max(photo["sizes"], key=lambda x: x["height"])["url"]
                                result.append({"type": "photo", "url": url})
                            elif attach["type"] == "video":
                                video = attach["video"]
                                if video.get("platform"):  # Только видео с платформ
                                    result.append({"type": "video", "url": video["player"]})
            except Exception as e:
                print(f"Ошибка при парсинге паблика {public_id}: {e}")
        return result[:count]

# Инициализация парсера VK
vk_parser = VKParser() if VK_TOKEN else None

# Обновленная клавиатура
def main_keyboard():
    buttons = [
        [InlineKeyboardButton("🎲 Идея", callback_data='idea'),
         InlineKeyboardButton("📍 Место", callback_data='place')],
        [InlineKeyboardButton("🕹 Игра", callback_data='game'),
         InlineKeyboardButton("🤖 ИИ-чат", callback_data='ai_chat')]
    ]
    if vk_parser:
        buttons.append([InlineKeyboardButton("🖼 Мемы (5 шт)", callback_data='memes')])
    return InlineKeyboardMarkup(buttons)

def ai_chat_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Выйти из ИИ-чата", callback_data='exit_ai')]
    ])

# ИИ-функционал (оставляем ваш существующий код без изменений)
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
                "temperature": 1.0
            },
            timeout=20
        )

        answer = response.json()['choices'][0]['message']['content']

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

# Обработчики (добавляем новый case для мемов)
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
    
    elif query.data == 'memes' and vk_parser:
        content = vk_parser.get_safe_content()
        if not content:
            await query.edit_message_text("😔 Мемы временно недоступны", reply_markup=main_keyboard())
            return
            
        for item in content:
            if item["type"] == "photo":
                await query.message.reply_photo(photo=item["url"])
            elif item["type"] == "video":
                await query.message.reply_video(video=item["url"], supports_streaming=True)
        
        await query.message.reply_text("Вот свежие мемы! Что еще хотите?", reply_markup=main_keyboard())
        return

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

# Остальные обработчики остаются без изменений
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Привет! Я умный бот-помощник:\n"
        "- Генератор идей\n"
        "- Поиск мест\n"
        "- Игры\n"
        "- Продвинутый ИИ-чат" + 
        ("\n- Свежие мемы" if vk_parser else ""),
        reply_markup=main_keyboard()
    )
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

# Настройка ConversationHandler (без изменений)
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
