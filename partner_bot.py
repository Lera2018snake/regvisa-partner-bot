import os
import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# === НАСТРОЙКИ (берутся из переменных окружения) ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

if not BOT_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не задана!")
if not ADMIN_ID:
    raise ValueError("Переменная окружения ADMIN_ID не задана!")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# === БАЗА ДАННЫХ ===
conn = sqlite3.connect('partners.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS partners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    name TEXT,
    company TEXT,
    contact TEXT,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
conn.commit()

# === СОСТОЯНИЯ ===
class PartnerForm(StatesGroup):
    name = State()
    company = State()
    contact = State()
    comment = State()

class QuestionForm(StatesGroup):
    text = State()

# === СТАРТ ===
@dp.message(Command("start"))
async def start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤝 Стать партнёром", callback_data="partner")],
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="question")],
        [InlineKeyboardButton(text="📢 Наш канал", url="https://t.me/regvisa")]
    ])
    await message.answer(
        "Здравствуйте! Это бот для партнёров Regvisa.\n"
        "Мы делаем сервис экспортного скрининга для IT.\n\n"
        "Выберите действие:",
        reply_markup=kb
    )

# === ЗАЯВКА ПАРТНЁРА ===
@dp.callback_query(F.data == "partner")
async def partner_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Как вас зовут?")
    await state.set_state(PartnerForm.name)
    await callback.answer()

@dp.message(PartnerForm.name)
async def partner_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Название компании или юрфирмы?")
    await state.set_state(PartnerForm.company)

@dp.message(PartnerForm.company)
async def partner_company(message: Message, state: FSMContext):
    await state.update_data(company=message.text)
    await message.answer("Контакт для связи (email, телефон, Telegram):")
    await state.set_state(PartnerForm.contact)

@dp.message(PartnerForm.contact)
async def partner_contact(message: Message, state: FSMContext):
    await state.update_data(contact=message.text)
    await message.answer("Комментарий или вопрос (или напишите «-»):")
    await state.set_state(PartnerForm.comment)

@dp.message(PartnerForm.comment)
async def partner_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or ""
    comment = message.text

    cursor.execute(
        "INSERT INTO partners (user_id, username, name, company, contact, comment) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, username, data['name'], data['company'], data['contact'], comment)
    )
    conn.commit()

    admin_text = (
        f"🤝 Новая заявка на партнёрство!\n\n"
        f"Имя: {data['name']}\n"
        f"Компания: {data['company']}\n"
        f"Контакт: {data['contact']}\n"
        f"Комментарий: {comment}\n\n"
        f"User ID: {user_id}\n"
        f"Username: @{username}"
    )
    await bot.send_message(ADMIN_ID, admin_text)
    await message.answer("Спасибо! Мы получили вашу заявку и свяжемся с вами в ближайшее время.")

# === ВОПРОС ===
@dp.callback_query(F.data == "question")
async def question_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите ваш вопрос, и мы ответим вам в ближайшее время.")
    await state.set_state(QuestionForm.text)
    await callback.answer()

@dp.message(QuestionForm.text)
async def question_text(message: Message, state: FSMContext):
    await state.clear()
    admin_text = f"❓ Вопрос от @{message.from_user.username or message.from_user.id}:\n{message.text}"
    await bot.send_message(ADMIN_ID, admin_text)
    await message.answer("Спасибо! Ваш вопрос отправлен, мы ответим в ближайшее время.")

# === КОМАНДА ДЛЯ АДМИНА ===
@dp.message(Command("partners"))
async def list_partners(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT name, company, contact, created_at FROM partners ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    if not rows:
        await message.answer("Пока нет заявок.")
        return
    text = "Последние 10 заявок:\n\n" + "\n".join(
        [f"{r[0]} | {r[1]} | {r[2]} | {r[3]}" for r in rows]
    )
    await message.answer(text)

# === ЗАПУСК ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
