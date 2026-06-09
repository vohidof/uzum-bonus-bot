import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import database
from texts import MESSAGES

print("Бот успешно запущен!")

# Получаем токен из переменных окружения
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: Message):
    # Инициализируем базу данных при первом запуске
    await database.init_db()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
         InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz")]
    ])
    await message.answer("Здравствуйте! / Assalomu alaykum!\nВыберите язык / Tilni tanlang:", reply_markup=kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(callback: CallbackQuery):
    lang = callback.data.split("_")[1]
    # Сохраняем язык в БД
    await database.set_lang(callback.from_user.id, lang)
    
    # ОТВЕТ БОТА ПОСЛЕ ВЫБОРА
    await callback.message.answer(MESSAGES[lang]['choice'])
    await callback.answer() # Чтобы убрать "часики" на кнопке

# ВАЖНО: Добавим обработчик на любое текстовое сообщение, чтобы бот не молчал
@dp.message()
async def handle_message(message: Message):
    # Бот просто будет отвечать, что он работает
    await message.answer("Пожалуйста, используйте кнопки для управления.")

async def main():
    # Удаляем старые сообщения (webhook) перед запуском
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
