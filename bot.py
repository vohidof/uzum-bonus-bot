import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, InputMediaPhoto, BotCommand, BotCommandScopeDefault, BotCommandScopeChat
import database
from texts import MESSAGES

class BotStates(StatesGroup):
    waiting_for_order_data = State()   
    waiting_for_review_photo = State() 
    waiting_for_promo = State()        

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())
ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) 

async def update_user_menu(user_id: int, lang: str):
    commands = [
        BotCommand(command="promo", description=MESSAGES[lang]['menu_promo']),
        BotCommand(command="lang", description=MESSAGES[lang]['menu_lang'])
    ]
    # ТЕПЕРЬ ТУТ ДИНАМИЧЕСКИЙ ПЕРЕВОД ДЛЯ АДМИНА КНОПКИ /admin
    if user_id == ADMIN_ID:
        commands.append(BotCommand(command="admin", description=MESSAGES[lang]['menu_admin']))
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=user_id))
    except Exception as e:
        print(f"Ошибка обновления меню для {user_id}: {e}")

# --- КОМАНДЫ БОТА ---

@dp.message(Command("lang"))
async def lang_cmd(message: Message, state: FSMContext):
    await state.clear() 
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="menulang_ru"),
         InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="menulang_uz")]
    ])
    await message.answer("Выберите язык / Tilni tanlang:", reply_markup=kb)

@dp.message(Command("promo"))
async def promo_cmd(message: Message, state: FSMContext):
    await state.clear()
    lang = await database.get_lang(message.from_user.id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['btn_order_num'], callback_data="method_number"),
         InlineKeyboardButton(text=MESSAGES[lang]['btn_screenshot'], callback_data="method_photo")]
    ])
    await message.answer(MESSAGES[lang]['choice_method'], reply_markup=kb)

@dp.message(Command("admin"))
async def admin_panel_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🔧 **Панель администратора GazpromBonus**\n\nВы находитесь в режиме управления. Все поступающие заявки будут отображаться ниже.")

@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="initlang_ru"),
         InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="initlang_uz")]
    ])
    await message.answer("Здравствуйте! / Assalomu alaykum!\nВыберите язык / Tilni tanlang:", reply_markup=kb)

# --- ОБРАБОТКА ВЫБОРА ЯЗЫКА ---
@dp.callback_query(F.data.startswith("initlang_") | F.data.startswith("menulang_"))
async def set_language(callback: CallbackQuery, state: FSMContext):
    action, lang = callback.data.split("_")
    await database.set_lang(callback.from_user.id, lang)
    await update_user_menu(callback.from_user.id, lang)
    
    # Если переключается админ — просто выводим уведомление и завершаем
    if callback.from_user.id == ADMIN_ID:
        await callback.message.edit_text(MESSAGES[lang]['lang_changed_admin'], reply_markup=None)
        await callback.answer()
        return

    # Логика для обычных пользователей
    if action == "initlang":
        await callback.message.edit_text(MESSAGES[lang]['lang_selected'], reply_markup=None)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=MESSAGES[lang]['btn_order_num'], callback_data="method_number"),
             InlineKeyboardButton(text=MESSAGES[lang]['btn_screenshot'], callback_data="method_photo")]
        ])
        await callback.message.answer(MESSAGES[lang]['choice_method'], reply_markup=kb)
    else:
        await callback.message.edit_text(MESSAGES[lang]['lang_changed_menu'], reply_markup=None, parse_mode="Markdown")
        
    await callback.answer()

# --- ОСТАЛЬНАЯ ЛОГИКА ---

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
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Одобрить ✅", callback_data=f"adm_app_{message.from_user.id}"),
         InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_rej_{message.from_user.id}")]
    ])
    
    admin_text = f"📥 **Новая заявка!**\n👤 Пользователь: @{message.from_user.username or 'без юзернейма'} (ID: {message.from_user.id})\n"
    
    if method == "number":
        admin_text += f"🔢 Номер заказа: `{order_info}`\n"
        await bot.send_photo(chat_id=ADMIN_ID, photo=review_photo_id, caption=admin_text + "\n📸 Фото отзыва выше:", reply_markup=admin_kb)
    else:
        admin_text += f"📸 Способ подтверждения: Скриншоты заказа и отзыва\n"
        media_group = [
            InputMediaPhoto(media=order_info, caption="1️⃣ Скриншот заказа"),
            InputMediaPhoto(media=review_photo_id, caption="2️⃣ Скриншот отзыва")
        ]
        await bot.send_media_group(chat_id=ADMIN_ID, media=media_group)
        await bot.send_message(chat_id=ADMIN_ID, text=admin_text + "\n👇 Выберите действие:", reply_markup=admin_kb)

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
    await database.init_db()
    
    default_commands = [
        BotCommand(command="promo", description="Получить промокод / Promokod olish"),
        BotCommand(command="lang", description="Сменить язык / Tilni o'zgartirish")
    ]
    await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())
    
    if ADMIN_ID != 0:
        await update_user_menu(ADMIN_ID, "ru")
        
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
