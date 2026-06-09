import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import database
from texts import MESSAGES

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
ADMIN_ID = 5075674162  # <--- ВСТАВЬТЕ СЮДА ВАШ ID В ТЕЛЕГРАМЕ

@dp.message(Command("start"))
async def start(message: Message):
    await database.init_db()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
         InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz")]
    ])
    await message.answer("Здравствуйте! / Assalomu alaykum!\nВыберите язык / Tilni tanlang:", reply_markup=kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(callback: CallbackQuery):
    lang = callback.data.split("_")[1]
    await database.set_lang(callback.from_user.id, lang)
    await callback.message.answer(MESSAGES[lang]['choice'])

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
