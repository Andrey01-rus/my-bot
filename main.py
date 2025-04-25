from flask import Flask
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

# Инициализация Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Бот активен!"

# Константы
AI_CHAT = 1
VK_TOKEN = os.getenv("VK_TOKEN")  # Токен VK API
SAFE_PUBLICS = [-97216585, -34317336, -34017843]  # Безопасные паблики: @video, @tnt, @lentach

# Класс для работы с VK
class VKMemes:
    def __init__(self):
        self.vk = vk_api.VkApi(token=VK_TOKEN)
        
    def get_memes(self, count=5):
        """Получает безопасные мемы из VK"""
        memes = []
        for public_id in SAFE_PUBLICS:
            try:
                posts = self.vk.method("wall.get", {
                    "owner_id": public_id,
                    "count": 20,
                    "filter": "owner"
                })["items"]
                
                for post in posts:
                    if len(memes) >= count:
                        break
                    if "attachments" in post:
                        for attach in post["attachments"]:
                            if attach["type"] == "photo":
                                photo = attach["photo"]
                                url = max(photo["sizes"], key=lambda x: x["height"])["url"]
                                memes.append({
                                    "type": "photo",
                                    "url": url,
                                    "source": f"https://vk.com/wall{post['owner_id']}_{post['id']}"
                                })
            except Exception as e:
                print(f"Ошибка VK: {e}")
        return memes[:count]

# Инициализация парсера VK
vk_parser = VKMemes() if VK_TOKEN else None

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
         InlineKeyboardButton("🤖 ИИ-чат", callback_data='ai_chat')]
    ]
    if vk_parser:
        buttons.append([InlineKeyboardButton("🖼 Мемы из VK (5 шт)", callback_data='vk_memes')])
    return InlineKeyboardMarkup(buttons)

def ai_chat_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Выйти из ИИ-чата", callback_data='exit_ai')]
    ])

# Обработчики
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Привет! Я умный бот-помощник:\n"
        "- Генератор идей\n"
        "- Поиск мест\n"
        "- Игры\n"
        "- Продвинутый ИИ-чат" + 
        ("\n- Свежие мемы из VK" if vk_parser else ""),
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

async def send_vk_memes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not vk_parser:
        await query.edit_message_text("⚠️ Функция мемов отключена", reply_markup=main_keyboard())
        return
    
    try:
        memes = vk_parser.get_memes()
        if not memes:
            await query.edit_message_text("😔 Не удалось загрузить мемы", reply_markup=main_keyboard())
            return
            
        for meme in memes:
            if meme["type"] == "photo":
                await query.message.reply_photo(
                    photo=meme["url"],
                    caption=f"Источник: {meme['source']}"
                )
                
        await query.message.reply_text(
            "Вот свежие мемы! Что еще хотите?",
            reply_markup=main_keyboard()
        )
    except Exception as e:
        print(f"Ошибка отправки мемов: {e}")
        await query.edit_message_text("⚠️ Ошибка загрузки мемов", reply_markup=main_keyboard())

# ... (остальные обработчики остаются без изменений)

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
    bot_app.add_handler(CallbackQueryHandler(send_vk_memes, pattern='^vk_memes$'))
    
    print("🤖 Бот запущен и готов к работе!")
    bot_app.run_polling(drop_pending_updates=True)
