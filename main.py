import asyncio
import json
import os
from typing import Optional
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ============ КОНФИГУРАЦИЯ ============
BOT_TOKEN = "8251591763:AAEpZxyGr3pW91CwDBfDehOv3Pm_Xaz4Ao8"  # Замените на токен вашего бота
DB_FILE = "database.json"


# ============ FSM СОСТОЯНИЯ ============
class AdminStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_description = State()
    waiting_for_code = State()
    waiting_for_delete_code = State()
    waiting_for_channel_id = State()
    waiting_for_channel_url = State()
    waiting_for_welcome_text = State()
    waiting_for_welcome_photo = State()


# ============ БАЗА ДАННЫХ ============
class Database:
    def __init__(self, filename: str):
        self.filename = filename
        self.data = self.load()

    def load(self) -> dict:
        """Загрузка БД из файла"""
        if os.path.exists(self.filename):
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Создание БД по умолчанию
            default_data = {
                "settings": {
                    "channel_id": "@allanimefilms",  # Замените на ID вашего канала
                    "channel_url": "https://t.me/allanimefilms",
                    "welcome_text": "👋 <b>Добро пожаловать!</b>\n\n🎬 Я помогу найти аниме, фильмы и манхву/мангу по коду.\n\n📝 Отправь мне код для поиска!",
                    "welcome_photo": None
                },
                "admins": [8429170216],  # Замените на ваш Telegram ID
                "content": {}
            }
            self.save(default_data)
            return default_data

    def save(self, data: Optional[dict] = None):
        """Сохранение БД в файл"""
        if data is None:
            data = self.data
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь админом"""
        return user_id in self.data["admins"]

    def add_content(self, code: str, photo_id: str, description: str):
        """Добавление контента"""
        self.data["content"][code] = {
            "photo_id": photo_id,
            "description": description
        }
        self.save()

    def get_content(self, code: str) -> Optional[dict]:
        """Получение контента по коду"""
        return self.data["content"].get(code)

    def delete_content(self, code: str) -> bool:
        """Удаление контента"""
        if code in self.data["content"]:
            del self.data["content"][code]
            self.save()
            return True
        return False

    def get_all_codes(self) -> list:
        """Получение всех кодов"""
        return list(self.data["content"].keys())

    def update_setting(self, key: str, value):
        """Обновление настройки"""
        self.data["settings"][key] = value
        self.save()

    def get_setting(self, key: str):
        """Получение настройки"""
        return self.data["settings"].get(key)


# ============ ИНИЦИАЛИЗАЦИЯ ============
db = Database(DB_FILE)
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()


# ============ КЛАВИАТУРЫ ============
def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для проверки подписки"""
    channel_url = db.get_setting("channel_url")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться", url=channel_url)],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")]
    ])


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Главное меню админ-панели"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить контент", callback_data="admin_add")],
        [InlineKeyboardButton(text="🗑 Удалить контент", callback_data="admin_delete")],
        [InlineKeyboardButton(text="⚙️ Настройки канала", callback_data="admin_channel")],
        [InlineKeyboardButton(text="💬 Настройки приветствия", callback_data="admin_welcome")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
    ])


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")]
    ])


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_menu")]
    ])


# ============ ПРОВЕРКА ПОДПИСКИ ============
async def check_user_subscription(user_id: int) -> bool:
    """Проверка подписки пользователя на канал"""
    channel_id = db.get_setting("channel_id")
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Ошибка проверки подписки: {e}")
        return False


# ============ ОБРАБОТЧИКИ КОМАНД ============
@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id

    # Проверка подписки
    is_subscribed = await check_user_subscription(user_id)

    if not is_subscribed:
        await message.answer(
            "⚠️ <b>Для использования бота необходимо подписаться на наш канал!</b>\n\n"
            "После подписки нажмите кнопку ниже:",
            reply_markup=get_subscription_keyboard()
        )
        return

    # Отправка приветствия
    welcome_text = db.get_setting("welcome_text")
    welcome_photo = db.get_setting("welcome_photo")

    if welcome_photo:
        try:
            await message.answer_photo(
                photo=welcome_photo,
                caption=welcome_text
            )
        except:
            await message.answer(welcome_text)
    else:
        await message.answer(welcome_text)


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery):
    """Проверка подписки по нажатию кнопки"""
    user_id = callback.from_user.id

    is_subscribed = await check_user_subscription(user_id)

    if is_subscribed:
        await callback.message.delete()

        welcome_text = db.get_setting("welcome_text")
        welcome_photo = db.get_setting("welcome_photo")

        if welcome_photo:
            try:
                await callback.message.answer_photo(
                    photo=welcome_photo,
                    caption="✅ <b>Спасибо за подписку!</b>\n\n" + welcome_text
                )
            except:
                await callback.message.answer("✅ <b>Спасибо за подписку!</b>\n\n" + welcome_text)
        else:
            await callback.message.answer("✅ <b>Спасибо за подписку!</b>\n\n" + welcome_text)
    else:
        await callback.answer("❌ Вы не подписаны на канал!", show_alert=True)


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ-панель"""
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔️ У вас нет доступа к админ-панели!")
        return

    await message.answer(
        "🔧 <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_keyboard()
    )


# ============ АДМИН МЕНЮ ============
@router.callback_query(F.data == "admin_menu")
async def admin_menu_callback(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню админки"""
    await state.clear()
    await callback.message.edit_text(
        "🔧 <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_keyboard()
    )


@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery):
    """Статистика"""
    total_content = len(db.data["content"])
    codes = ", ".join(db.get_all_codes()[:10]) if db.get_all_codes() else "нет"

    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"📦 Всего контента: <b>{total_content}</b>\n"
        f"🔢 Коды: <code>{codes}</code>"
    )

    if total_content > 10:
        text += "\n<i>... и другие</i>"

    await callback.message.edit_text(text, reply_markup=get_back_keyboard())


# ============ ДОБАВЛЕНИЕ КОНТЕНТА ============
@router.callback_query(F.data == "admin_add")
async def admin_add_callback(callback: CallbackQuery, state: FSMContext):
    """Начало добавления контента"""
    await callback.message.edit_text(
        "📸 <b>Добавление контента</b>\n\n"
        "Отправьте фото/постер контента:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_photo)


@router.message(AdminStates.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Получение фото"""
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)

    await message.answer(
        "📝 <b>Отлично!</b>\n\n"
        "Теперь отправьте описание контента:\n"
        "<i>Название, жанр, описание и т.д.</i>\n\n"
        "Используйте HTML-теги для форматирования:\n"
        "<code>&lt;b&gt;жирный&lt;/b&gt;</code>\n"
        "<code>&lt;i&gt;курсив&lt;/i&gt;</code>",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_description)


@router.message(AdminStates.waiting_for_photo)
async def invalid_photo(message: Message):
    """Неверный формат фото"""
    await message.answer("❌ Пожалуйста, отправьте фото!")


@router.message(AdminStates.waiting_for_description, F.text)
async def process_description(message: Message, state: FSMContext):
    """Получение описания"""
    await state.update_data(description=message.text)

    await message.answer(
        "🔢 <b>Последний шаг!</b>\n\n"
        "Введите уникальный код для этого контента:\n"
        "<i>(только цифры, например: 12345)</i>",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_code)


@router.message(AdminStates.waiting_for_code, F.text)
async def process_code(message: Message, state: FSMContext):
    """Получение кода и сохранение"""
    code = message.text.strip()

    if not code.isdigit():
        await message.answer("❌ Код должен содержать только цифры! Попробуйте еще раз:")
        return

    if db.get_content(code):
        await message.answer("⚠️ Контент с таким кодом уже существует! Введите другой код:")
        return

    data = await state.get_data()
    db.add_content(code, data['photo_id'], data['description'])

    await message.answer(
        f"✅ <b>Контент успешно добавлен!</b>\n\n"
        f"🔢 Код: <code>{code}</code>",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()


# ============ УДАЛЕНИЕ КОНТЕНТА ============
@router.callback_query(F.data == "admin_delete")
async def admin_delete_callback(callback: CallbackQuery, state: FSMContext):
    """Начало удаления контента"""
    codes = db.get_all_codes()

    if not codes:
        await callback.message.edit_text(
            "📭 <b>База данных пуста</b>\n\n"
            "Нет контента для удаления.",
            reply_markup=get_back_keyboard()
        )
        return

    codes_text = ", ".join(codes[:20])
    await callback.message.edit_text(
        f"🗑 <b>Удаление контента</b>\n\n"
        f"Доступные коды: <code>{codes_text}</code>\n\n"
        f"Отправьте код контента для удаления:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_delete_code)


@router.message(AdminStates.waiting_for_delete_code, F.text)
async def process_delete_code(message: Message, state: FSMContext):
    """Удаление контента по коду"""
    code = message.text.strip()

    if db.delete_content(code):
        await message.answer(
            f"✅ <b>Контент удален!</b>\n\n"
            f"🔢 Код: <code>{code}</code>",
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer(
            f"❌ <b>Контент не найден!</b>\n\n"
            f"Код <code>{code}</code> не существует в базе.",
            reply_markup=get_back_keyboard()
        )

    await state.clear()


# ============ НАСТРОЙКИ КАНАЛА ============
@router.callback_query(F.data == "admin_channel")
async def admin_channel_callback(callback: CallbackQuery):
    """Меню настроек канала"""
    channel_id = db.get_setting("channel_id")
    channel_url = db.get_setting("channel_url")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆔 Изменить ID канала", callback_data="change_channel_id")],
        [InlineKeyboardButton(text="🔗 Изменить ссылку", callback_data="change_channel_url")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")]
    ])

    await callback.message.edit_text(
        f"⚙️ <b>Настройки канала</b>\n\n"
        f"🆔 ID: <code>{channel_id}</code>\n"
        f"🔗 Ссылка: {channel_url}",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "change_channel_id")
async def change_channel_id_callback(callback: CallbackQuery, state: FSMContext):
    """Изменение ID канала"""
    await callback.message.edit_text(
        "🆔 <b>Изменение ID канала</b>\n\n"
        "Отправьте новый ID канала:\n"
        "<i>Например: @channel или -100123456789</i>",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_channel_id)


@router.message(AdminStates.waiting_for_channel_id, F.text)
async def process_channel_id(message: Message, state: FSMContext):
    """Сохранение нового ID канала"""
    channel_id = message.text.strip()
    db.update_setting("channel_id", channel_id)

    await message.answer(
        f"✅ <b>ID канала обновлен!</b>\n\n"
        f"Новый ID: <code>{channel_id}</code>",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()


@router.callback_query(F.data == "change_channel_url")
async def change_channel_url_callback(callback: CallbackQuery, state: FSMContext):
    """Изменение ссылки канала"""
    await callback.message.edit_text(
        "🔗 <b>Изменение ссылки канала</b>\n\n"
        "Отправьте новую ссылку:\n"
        "<i>Например: https://t.me/channel</i>",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_channel_url)


@router.message(AdminStates.waiting_for_channel_url, F.text)
async def process_channel_url(message: Message, state: FSMContext):
    """Сохранение новой ссылки канала"""
    channel_url = message.text.strip()
    db.update_setting("channel_url", channel_url)

    await message.answer(
        f"✅ <b>Ссылка обновлена!</b>\n\n"
        f"Новая ссылка: {channel_url}",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()


# ============ НАСТРОЙКИ ПРИВЕТСТВИЯ ============
@router.callback_query(F.data == "admin_welcome")
async def admin_welcome_callback(callback: CallbackQuery):
    """Меню настроек приветствия"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Изменить текст", callback_data="change_welcome_text")],
        [InlineKeyboardButton(text="🖼 Изменить фото", callback_data="change_welcome_photo")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")]
    ])

    await callback.message.edit_text(
        "💬 <b>Настройки приветствия</b>\n\n"
        "Выберите, что хотите изменить:",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "change_welcome_text")
async def change_welcome_text_callback(callback: CallbackQuery, state: FSMContext):
    """Изменение текста приветствия"""
    current_text = db.get_setting("welcome_text")
    await callback.message.edit_text(
        f"💬 <b>Изменение текста приветствия</b>\n\n"
        f"Текущий текст:\n{current_text}\n\n"
        f"Отправьте новый текст:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_welcome_text)


@router.message(AdminStates.waiting_for_welcome_text, F.text)
async def process_welcome_text(message: Message, state: FSMContext):
    """Сохранение нового текста приветствия"""
    new_text = message.text
    db.update_setting("welcome_text", new_text)

    await message.answer(
        "✅ <b>Текст приветствия обновлен!</b>",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()


@router.callback_query(F.data == "change_welcome_photo")
async def change_welcome_photo_callback(callback: CallbackQuery, state: FSMContext):
    """Изменение фото приветствия"""
    await callback.message.edit_text(
        "🖼 <b>Изменение фото приветствия</b>\n\n"
        "Отправьте новое фото или напишите <code>удалить</code> для удаления:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_welcome_photo)


@router.message(AdminStates.waiting_for_welcome_photo, F.photo)
async def process_welcome_photo(message: Message, state: FSMContext):
    """Сохранение нового фото приветствия"""
    photo_id = message.photo[-1].file_id
    db.update_setting("welcome_photo", photo_id)

    await message.answer(
        "✅ <b>Фото приветствия обновлено!</b>",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()


@router.message(AdminStates.waiting_for_welcome_photo, F.text)
async def remove_welcome_photo(message: Message, state: FSMContext):
    """Удаление фото приветствия"""
    if message.text.lower() == "удалить":
        db.update_setting("welcome_photo", None)
        await message.answer(
            "✅ <b>Фото приветствия удалено!</b>",
            reply_markup=get_admin_keyboard()
        )
        await state.clear()
    else:
        await message.answer("❌ Отправьте фото или напишите <code>удалить</code>")


# ============ ПОИСК КОНТЕНТА ============
@router.message(F.text)
async def search_content(message: Message):
    """Поиск контента по коду"""
    # Проверка подписки
    is_subscribed = await check_user_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            "⚠️ <b>Для использования бота необходимо подписаться на наш канал!</b>",
            reply_markup=get_subscription_keyboard()
        )
        return

    code = message.text.strip()

    # Проверка, что это число
    if not code.isdigit():
        await message.answer(
            "❌ <b>Неверный формат!</b>\n\n"
            "Пожалуйста, отправьте числовой код.\n"
            "<i>Например: 12345</i>"
        )
        return

    # Поиск в БД
    content = db.get_content(code)

    if content:
        try:
            await message.answer_photo(
                photo=content['photo_id'],
                caption=f"🔍 <b>Найдено!</b>\n\n{content['description']}\n\n🔢 Код: <code>{code}</code>"
            )
        except Exception as e:
            await message.answer(
                f"✅ <b>Контент найден!</b>\n\n"
                f"{content['description']}\n\n"
                f"🔢 Код: <code>{code}</code>\n\n"
                f"<i>⚠️ Ошибка загрузки фото</i>"
            )
    else:
        await message.answer(
            f"❌ <b>Контент не найден</b>\n\n"
            f"Код <code>{code}</code> отсутствует в базе данных."
        )


# ============ ЗАПУСК БОТА ============
async def main():
    """Главная функция запуска бота"""
    dp.include_router(router)

    print("🤖 Бот запущен!")
    print(f"📊 Загружено контента: {len(db.data['content'])}")
    print(f"👥 Админов: {len(db.data['admins'])}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())