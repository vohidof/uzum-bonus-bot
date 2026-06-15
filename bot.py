import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import database
from texts import MESSAGES

# Состояния бота (FSM)
class BotStates(StatesGroup):
    waiting_for_order_data = State()   # Ожидание номера или фото заказа
    waiting_for_review_photo = State() # Ожидание фото отзыва
    waiting_for_promo = State()        # Админ вводит промокод

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())
ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) # Берем ID админа из настроек Railway

@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    await database.init_db()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Sub/Follow 🇷🇺 Русский", callback_data="lang_ru"),
         InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz")]
    ])
    await message.answer("Здравствуйте! / Assalomu alaykum!\nВыберите язык / Tilni tanlang:", reply_markup=kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    await database.set_lang(callback.from_user.id, lang)
    
    # Меняем старый текст (подтверждаем выбор языка)
    await callback.message.edit_text(MESSAGES[lang]['lang_selected'], reply_markup=None)
    
    # Отправляем НОВОЕ сообщение со всеми кнопками выбора метода
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['btn_order_num'], callback_data="method_number"),
         InlineKeyboardButton(text=MESSAGES[lang]['btn_screenshot'], callback_data="method_photo")]
    ])
    await callback.message.answer(MESSAGES[lang]['choice_method'], reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("method_"))
async def choose_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split("_")[1]
    lang = await database.get_lang(callback.from_user.id)
    await state.update_data(chosen_method=method)
    
    if method == "number":
        await callback.message.answer(MESSAGES[lang]['ask_order_num'])
    else:
        await callback.message.answer(MESSAGES[lang]['ask_order_screen'])
        
    await state.set_state(BotStates.waiting_for_order_data)
    await callback.answer()

@dp.message(BotStates.waiting_for_order_data)
async def process_order_data(message: Message, state: FSMContext):
    lang = await database.get_lang(message.from_user.id)
    data = await state.get_data()
    method = data.get("chosen_method")
    
    if method == "number":
        if not message.text or not message.text.isdigit():
            await message.answer(MESSAGES[lang]['invalid_number'])
            return
        await state.update_data(order_info=message.text)
    else:
        if not message.photo:
            await message.answer(MESSAGES[lang]['invalid_photo'])
            return
        await state.update_data(order_info=message.photo[-1].file_id)
        
    await message.answer(MESSAGES[lang]['ask_review_screen'])
    await state.set_state(BotStates.waiting_for_review_photo)

@dp.message(BotStates.waiting_for_review_photo)
async def process_review_photo(message: Message, state: FSMContext):
    lang = await database.get_lang(message.from_user.id)
    if not message.photo:
        await message.answer(MESSAGES[lang]['invalid_photo'])
        return
        
    review_photo_id = message.photo[-1].file_id
    user_data = await state.get_data()
    method = user_data.get("chosen_method")
    order_info = user_data.get("order_info")
    
    await message.answer(MESSAGES[lang]['success_user'])
    await state.clear()
    
    # Сборка заявки для АДМИНА
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Одобрить ✅", callback_data=f"adm_app_{message.from_user.id}"),
         InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_rej_{message.from_user.id}")]
    ])
    
    admin_text = f"📥 **Новая заявка!**\n👤 Пользователь: @{message.from_user.username or 'без юзернейма'} (ID: {message.from_user.id})\n"
    if method == "number":
        admin_text += f"🔢 Номер заказа: `{order_info}`\n"
        await bot.send_photo(chat_id=ADMIN_ID, photo=review_photo_id, caption=admin_text + "📸 Фото отзыва ниже:", reply_markup=admin_kb)
    else:
        admin_text += f"📸 Скриншот заказа и отзыва прикреплены ниже.\n"
        await bot.send_photo(chat_id=ADMIN_ID, photo=order_info, caption=admin_text + "1️⃣ Скриншот заказа:")
        await bot.send_photo(chat_id=ADMIN_ID, photo=review_photo_id, caption="2️⃣ Скриншот отзыва:", reply_markup=admin_kb)

# --- АДМИНСКАЯ ЛОГИКА ---
@dp.callback_query(F.data.startswith("adm_"))
async def admin_decision(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Вы не админ!", show_alert=True)
        return
        
    action = callback.data.split("_")[1]
    target_user_id = int(callback.data.split("_")[2])
    
    if action == "app":
        await callback.message.answer(f"Введите промокод для пользователя {target_user_id}:")
        await state.update_data(promo_target=target_user_id)
        await state.set_state(BotStates.waiting_for_promo)
    else:
        user_lang = await database.get_lang(target_user_id)
        await bot.send_message(chat_id=target_user_id, text=MESSAGES[user_lang]['rejected_user'])
        await callback.message.answer("Заявка отклонена.")
    await callback.answer()

@dp.message(BotStates.waiting_for_promo)
async def admin_send_promo(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
        
    data = await state.get_data()
    target_user_id = data.get("promo_target")
    promocode = message.text
    
    user_lang = await database.get_lang(target_user_id)
    text_to_user = MESSAGES[user_lang]['approved_user'].format(promocode=promocode)
    
    try:
        await bot.send_message(chat_id=target_user_id, text=text_to_user, parse_mode="Markdown")
        await message.answer(f"✅ Промокод успешно отправлен пользователю {target_user_id}!")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить сообщение: {e}")
        
    await state.clear()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
