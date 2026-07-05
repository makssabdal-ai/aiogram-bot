from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import Database
from utils.keyboards import Keyboards

router = Router()


def get_welcome_text(first_name: str) -> str:
    return (
        f"<b>Привет, {first_name}!</b>\n"
        f"Я <i>Poli</i>, новый телеграмм-бот.\n\n"
        f"Зачем я нужен? Отвечу просто — для удобства коммуникации и связи) 😉\n\n"
        f"Что здесь есть?\n\n"
        f"  • Каталог товаров \n"
        f"  • Мои работы \n"
        f"  • Ваши отзывы \n"
        f"  • Мои контакты \n"
        f"  • И возможность сделать заказ прямо здесь!\n\n"
        f"Устраиватесь поудобнее и давайте начнем наше сладкое путешествие! 🎂✨ \n\n"
        f"<i>created by Smirnov</i>"
    )


@router.message(Command("start"))
@router.message(F.text.lower() == "старт")
async def cmd_start(message: Message, db: Database):
    """Обработчик команды /start"""
    # Добавляем пользователя в базу данных при первом старте
    await db.add_user(
        telegram_id=message.from_user.id,
        fullname=message.from_user.first_name,
        username=message.from_user.username
    )

    await message.answer(get_welcome_text(message.from_user.first_name), reply_markup=Keyboards.get_main_menu(), parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = (
        "Список доступных команд:\n\n"
        "/start - Запустить бота и открыть меню\n"
        "/help - Получить список команд\n"
    )
    await message.answer(help_text, reply_markup=Keyboards.get_back_keyboard())


@router.callback_query(F.data == "back")
async def callback_back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню из любого раздела"""
    await callback.answer("Вы вернулись в главное меню.")
    await state.clear()  # Сбрасываем FSM, если пользователь решил выйти из формы
    await callback.message.answer("Главное меню:", reply_markup=Keyboards.get_main_menu())


@router.callback_query(F.data == "about")
async def callback_about(callback: CallbackQuery):
    """Раздел 'Обо мне'"""
    await callback.answer()
    about_text = (
        "Привет-привет! Я Полина. Пеку торты не по учебникам, а по любви 💗✨\n"
        "А этот бот — мой маленький помощник 🤖\n\n"
        "Первый раз испекла торт больше пяти лет назад — и затянуло 😊🍰\n"
        "На заказ работаю около двух лет, и за это время собрала не только навыки, "
        "но и искренние «спасибо» от клиентов. 🙏💕"
    )
    # Используйте ваш актуальный file_id фотографии
    photo_id = "AgACAgIAAxkBAAIJGmob31lGNiN9qux8qVYFTGuVK1RdAAI1HGsb1pfYSH2RxgvNHuh-AQADAgADeQADOwQ"

    try:
        await callback.message.answer_photo(
            photo=photo_id,
            caption=about_text,
            reply_markup=Keyboards.get_back_keyboard()
        )
    except Exception:
        # Фолбэк на случай, если file_id недействителен на другом токене
        await callback.message.answer(about_text, reply_markup=Keyboards.get_back_keyboard())


@router.callback_query(F.data == "contact_me")
async def callback_contacts(callback: CallbackQuery):
    """Раздел с контактами кондитера"""
    await callback.answer()
    contacts_text = (
        "Со мной можно связаться по следующим контактам:\n\n"
        "🔹 ТГ-аккаунт: @Sewwwqp\n"
        "🔹 Страница Вконтакте: https://vk.com/polya_smi\n"
        "🔹 Телеграм-канал: https://t.me/tortsm\n"
        "🔹 Сообщество Вконтакте: https://vk.com/club235221265\n\n"
        "Буду рада помочь Вам! 🤗"
    )
    await callback.message.answer(contacts_text, reply_markup=Keyboards.get_back_keyboard())
