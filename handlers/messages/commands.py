"""
Command and message handlers for text messages.
"""
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from database import Database
from forms.user import Form
from handlers.keyboards.main import Keyboards
from utils.validators import Validators


router = Router()

# Global database instance
db: Database = None
# Keyboard and validator instances
kb = Keyboards()
validator = Validators()


def setup_database(database: Database) -> None:
    """Set global database instance."""
    global db
    db = database


# ======================= COMMAND HANDLERS =======================

@router.message(Command("start"))
@router.message(F.text.lower() == "старт")
async def start(message: Message, state: FSMContext) -> None:
    """Handle /start command."""
    await db.add_user(
        telegram_id=message.from_user.id,
        fullname=message.from_user.first_name,
        username=message.from_user.username
    )

    await message.answer(
        f"<b>Привет, {message.from_user.first_name}!</b>\n"
        "Я <i>Poli</i>, новый телеграмм-бот\n\n"
        "Зачем я нужен?\n"
        "Отвечу просто — для удобства коммуникации и обратной связи)\n\n"
        "Что здесь есть?\n"
        "• каталог товаров\n"
        "• мои работы\n"
        "• ваши отзывы\n"
        "• мои контакты\n"
        "• и возможность сделать заказ прямо здесь\n\n"
        "В общем, устраивайся уютно — я постараюсь быть полезным 😌",
        parse_mode="HTML",
        reply_markup=kb.get_main_menu()
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    """Handle /help command."""
    await message.answer(
        "Список команд:\n\n"
        "/start - Запустить бота\n"
        "/help - Получить список команд\n",
        reply_markup=kb.get_back_keyboard()
    )


# ======================= ORDER FORM HANDLERS =======================

@router.message(StateFilter(Form.fullname), F.text)
async def process_fullname(message: Message, state: FSMContext) -> None:
    """Process fullname input."""
    is_valid, result = validator.validate_fullname(message.text)

    if not is_valid:
        await message.answer(result)
        return

    await state.update_data(fullname=message.text)
    await state.set_state(Form.phone_number)
    await message.answer("Теперь введите Ваш номер телефона:")


@router.message(StateFilter(Form.phone_number), F.text)
async def process_phone_number(message: Message, state: FSMContext) -> None:
    """Process phone number input."""
    is_valid, result = validator.validate_phone(message.text)

    if not is_valid:
        await message.answer(result)
        return

    await state.update_data(phone_number=result)
    await state.set_state(Form.account)
    await message.answer("Теперь напишите ссылку на Ваш ВК/ТГ:")


@router.message(StateFilter(Form.account), F.text)
async def process_account(message: Message, state: FSMContext) -> None:
    """Process social account input."""
    is_valid, response = validator.validate_social_account(message.text)

    if not is_valid:
        await message.answer(response)
        return

    await state.update_data(account=message.text)
    await state.set_state(Form.cake)
    await message.answer("Теперь выберите торт:", reply_markup=kb.get_cake_choice())


@router.message(StateFilter(Form.media))
async def process_media(message: Message, state: FSMContext) -> None:
    """Process media input (photo/video)."""
    if message.photo:
        await state.update_data(
            media_type="photo",
            media=message.photo[-1].file_id
        )
    elif message.video:
        await state.update_data(
            media_type="video",
            media=message.video.file_id
        )
    elif message.text == "Пропустить":
        await state.update_data(media_type=None, media=None)
    else:
        await message.answer(
            "Отправьте фото или видео",
            reply_markup=kb.get_miss_keyboard()
        )
        return

    await state.set_state(Form.additional_info)
    await message.answer(
        "Если у Вас есть дополнительная информация или пожелания, пожалуйста, напишите.\n"
        "Если Вы выбрали доставку, пожалуйста, укажите адрес и время куда привезти заказ."
    )


@router.message(StateFilter(Form.additional_info))
async def process_additional_info(message: Message, state: FSMContext) -> None:
    """Process additional information and show order summary."""
    await state.update_data(additional_info=message.text)

    data = await state.get_data()

    # Format media type for display
    media_type = data.get("media_type")
    if media_type == "photo":
        media_text = "Фото"
    elif media_type == "video":
        media_text = "Видео"
    else:
        media_text = "не прикреплено"

    # Prepare order summary
    summary = (
        f"Проверьте созданную заявку:\n"
        f"ФИО: {data['fullname']}\n"
        f"Номер телефона: {data['phone_number']}\n"
        f"Аккаунт: {data['account']}\n"
        f"Торт: {data['cake']}\n"
        f"Размер: {data['size']}\n"
        f"Дата: {data['date_delivery']}\n"
        f"Способ доставки: {data['logistics']}\n"
        f"Медиавложения: {media_text}\n"
        f"Дополнительная информация: {data['additional_info']}"
    )

    await message.answer(summary, reply_markup=kb.get_check_keyboard())


# ======================= DEBUG HANDLERS =======================

@router.message(F.photo)
async def get_photo_id(message: Message) -> None:
    """Get photo file ID for admin purposes."""
    file_id = message.photo[-1].file_id
    await message.answer(f"file_id:\n{file_id}")


@router.message(F.video)
async def get_video_id(message: Message) -> None:
    """Get video file ID for admin purposes."""
    file_id = message.video.file_id
    await message.answer(f"file_id:\n{file_id}")


# ======================= DEFAULT HANDLER =======================

@router.message()
async def unknown_message(message: Message, state: FSMContext) -> None:
    """Handle unknown messages outside of form context."""
    current_state = await state.get_state()

    # If FSM is active, ignore the message
    if current_state:
        return

    await message.answer(
        "Извините, я не понимаю эту команду.\n"
        "Напишите /help для списка команд."
    )
