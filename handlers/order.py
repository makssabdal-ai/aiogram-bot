from os import getenv
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram_calendar import SimpleCalendarCallback, SimpleCalendar

from database.db import Database
from forms.user import Form
from utils.keyboards import Keyboards
from utils.validators import Validators
from utils.constants import CAKE_NAMES, SIZES, LOGISTICS

router = Router()


@router.callback_query(F.data == "make_order")
async def order_start(callback: CallbackQuery, state: FSMContext):
    """Начало цепочки заказа"""
    await callback.answer()
    await state.set_state(Form.fullname)
    await callback.message.answer(
        "Давайте создадим заявку Вашего заказа. Для начала введите Ваше ФИО:",
        reply_markup=Keyboards.get_back_keyboard()
    )


@router.message(StateFilter(Form.fullname), F.text)
async def process_fullname(message: Message, state: FSMContext):
    is_valid, result = Validators.validate_fullname(message.text)
    if not is_valid:
        await message.answer(result)
        return

    await state.update_data(fullname=message.text)
    await state.set_state(Form.phone_number)
    await message.answer("Теперь введите Ваш номер телефона:")


@router.message(StateFilter(Form.phone_number), F.text)
async def process_phone_number(message: Message, state: FSMContext):
    is_valid, result = Validators.validate_phone(message.text)
    if not is_valid:
        await message.answer(result)
        return

    await state.update_data(phone_number=result)
    await state.set_state(Form.account)
    await message.answer("Теперь напишите ссылку на Ваш ВК или юзернейм в ТГ:")


@router.message(StateFilter(Form.account), F.text)
async def process_account(message: Message, state: FSMContext):
    is_valid, response = Validators.validate_social_account(message.text)
    if not is_valid:
        await message.answer(response)
        return

    await state.update_data(account=message.text)
    await state.set_state(Form.cake)
    await message.answer("Теперь выберите торт из предложенных:", reply_markup=Keyboards.get_cake_choice())


@router.callback_query(Form.cake, F.data.startswith("cake_"))
async def process_cake_choice(callback: CallbackQuery, state: FSMContext):
    cake_choice = CAKE_NAMES[callback.data]
    await state.update_data(cake=cake_choice)

    await callback.answer()
    await state.set_state(Form.size)
    await callback.message.answer("Теперь выберите размер торта:", reply_markup=Keyboards.get_size_choice())


@router.callback_query(Form.size, F.data.startswith("size_"))
async def process_size_choice(callback: CallbackQuery, state: FSMContext):
    size_choice = SIZES[callback.data]
    await state.update_data(size=size_choice)

    await callback.answer()
    await state.set_state(Form.date)
    await callback.message.answer(
        "Выберите дату, к которой нужно приготовить торт:",
        reply_markup=await Keyboards.get_calendar()
    )


@router.callback_query(SimpleCalendarCallback.filter(), Form.date)
async def process_date_choice(callback: CallbackQuery, callback_data: SimpleCalendarCallback, state: FSMContext, db: Database):
    selected, date_selected = await SimpleCalendar().process_selection(callback, callback_data)
    if not selected:
        return

    is_valid, msg = Validators.validate_date(date_selected)
    if not is_valid:
        await callback.answer(msg, show_alert=True)
        await callback.message.answer("Выберите дату корректно (минимум через 3 дня):", reply_markup=await Keyboards.get_calendar())
        return

    formatted_date = date_selected.strftime("%d.%m.%Y")
    count = await db.count_orders_by_date(formatted_date)

    if count >= 3:
        await callback.answer("Эта дата уже полностью занята (лимит 3 заказа)", show_alert=True)
        await callback.message.answer("Пожалуйста, выберите другую дату:", reply_markup=await Keyboards.get_calendar())
        return

    await state.update_data(date_delivery=formatted_date)
    await state.set_state(Form.logistics)
    await callback.message.answer("Выберите способ доставки:", reply_markup=Keyboards.get_logistics_choice())


@router.callback_query(Form.logistics, F.data.startswith("logistics_"))
async def process_logistics_choice(callback: CallbackQuery, state: FSMContext):
    logistics_choice = LOGISTICS[callback.data]
    await state.update_data(logistics=logistics_choice)

    await callback.answer()
    await state.set_state(Form.media)
    await callback.message.answer("Вы можете отправить фото или видео референса:", reply_markup=Keyboards.get_miss_keyboard())


@router.callback_query(Form.media, F.data == "skip")
async def process_media_skip(callback: CallbackQuery, state: FSMContext):
    """Пропуск шага с референсом"""
    await callback.answer("Шаг пропущен.")
    await state.update_data(media_type=None, media=None)
    await state.set_state(Form.additional_info)
    await callback.message.answer(
        "Введите дополнительную информацию или пожелания (если есть):",
        reply_markup=Keyboards.get_miss_keyboard()
    )


@router.message(StateFilter(Form.media))
async def process_media_upload(message: Message, state: FSMContext):
    """Обработка отправленного медиафайла"""
    if message.photo:
        await state.update_data(media_type="photo", media=message.photo[-1].file_id)
    elif message.video:
        await state.update_data(media_type="video", media=message.video.file_id)
    else:
        await message.answer("Пожалуйста, отправьте фото, видео или нажмите кнопку 'Пропустить'", reply_markup=Keyboards.get_miss_keyboard())
        return

    await state.set_state(Form.additional_info)
    await message.answer(
        "Почти готово! Укажите дополнительную информацию (для доставки — точный адрес и время):",
        reply_markup=Keyboards.get_miss_keyboard()
    )


@router.message(StateFilter(Form.additional_info), F.text)
async def process_additional_info(message: Message, state: FSMContext):
    await state.update_data(additional_info=message.text)
    await send_order_summary(message, state)


@router.callback_query(Form.additional_info, F.data == "skip")
async def process_additional_info_skip(callback: CallbackQuery, state: FSMContext):
    """Пропуск шага с дополнительной информацией"""
    await callback.answer("Шаг пропущен.")
    await state.update_data(additional_info="Не указано")
    await send_order_summary(callback.message, state)


async def send_order_summary(message: Message, state: FSMContext):
    data = await state.get_data()

    media_text = "Фото" if data.get("media_type") == "photo" else "Видео" if data.get(
        "media_type") == "video" else "Не прикреплено"

    summary = (
        f"📋 <b>Проверьте вашу заявку:</b>\n\n"
        f"👤 ФИО: {data['fullname']}\n"
        f"📞 Телефон: {data['phone_number']}\n"
        f"🌐 Аккаунт: {data['account']}\n"
        f"🎂 Торт: {data['cake']}\n"
        f"⚖️ Размер: {data['size']}\n"
        f"📅 Забронированная дата: {data['date_delivery']}\n"
        f"🚗 Доставка: {data['logistics']}\n"
        f"🖼 Референс: {media_text}\n"
        f"📝 Комментарий: {data['additional_info']}"
    )
    await message.answer(summary, reply_markup=Keyboards.get_check_keyboard())


@router.callback_query(F.data == "confirm_order")
async def callback_confirm_order(callback: CallbackQuery, state: FSMContext, db: Database):
    """Подтверждение и отправка заказа администраторам"""
    await callback.answer()
    data = await state.get_data()

    if not data:
        await callback.message.answer("Ошибка сессии. Сформируйте заказ заново.")
        return

    # Сохраняем заказ в базу данных
    await db.add_order(telegram_id=callback.from_user.id, data=data)

    # Получаем строку со всеми ID из .env (например: "8983696498,123456789")
    admin_ids_raw = getenv("ADMIN_IDS", "")

    # Превращаем её в список чисел Python
    admin_ids = [int(x)
                 for x in admin_ids_raw.split(",") if x.strip().isdigit()]

    order_text = (
        f"🆕 <b>Новый заказ!</b>\n\n"
        f"ФИО: {data['fullname']}\n"
        f"Телефон: {data['phone_number']}\n"
        f"Аккаунт: {data['account']}\n\n"
        f"Торт: {data['cake']}\n"
        f"Размер: {data['size']}\n"
        f"Забронированная дата: {data['date_delivery']}\n"
        f"Логистика: {data['logistics']}\n\n"
        f"Доп. информация:\n{data['additional_info']}"
    )

    # Проходимся циклом по каждому ID и отправляем уведомление
    for admin_id in admin_ids:
        try:
            if data.get("media_type") == "photo":
                await callback.bot.send_photo(chat_id=admin_id, photo=data["media"], caption=order_text)
            elif data.get("media_type") == "video":
                # Исправлена опечатка aiogram: заменено photo= на video=
                await callback.bot.send_video(chat_id=admin_id, video=data["media"], caption=order_text)
            else:
                await callback.bot.send_message(chat_id=admin_id, text=order_text)
        except Exception as e:
            # Если один из админов заблокировал бота, цикл не прервется и отправит остальным
            print(
                f"[ERROR] Не удалось отправить сообщение админу {admin_id}: {e}")

    await state.clear()
    await callback.message.answer(
        text="Заказ принят! Скоро я свяжусь с вами для подтверждения 😊",
        reply_markup=Keyboards.get_back_keyboard()
    )


@router.callback_query(F.data == "edit_order")
async def callback_edit_order(callback: CallbackQuery, state: FSMContext):
    """Сброс и заполнение заново"""
    await callback.answer()
    await state.clear()
    await state.set_state(Form.fullname)
    await callback.message.answer("Давайте заполним заявку заново.\nВведите Ваше ФИО:", reply_markup=Keyboards.get_back_keyboard())


# Вспомогательные хэндлеры для извлечения ID медиа (утилиты администратора)
@router.message(F.photo)
async def get_photo_id(message: Message):
    await message.answer(f"<code>file_id:</code>\n{message.photo[-1].file_id}")


@router.message(F.video)
async def get_video_id(message: Message):
    await message.answer(f"<code>file_id:</code>\n{message.video.file_id}")


@router.message()
async def unknown_message(message: Message, state: FSMContext):
    if await state.get_state():
        return
    await message.answer("Извините, я не знаю такой команды.\nВведите /help для вызова меню.")
