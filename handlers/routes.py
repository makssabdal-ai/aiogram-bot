# ---------------------- Импортирование библиотек и файлов ----------------------
from os import getenv
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from forms.user import Form
from aiogram.fsm.context import FSMContext
from aiogram_calendar import SimpleCalendarCallback, SimpleCalendar
from aiogram.filters import StateFilter
from aiogram.types import InputMediaPhoto, InputMediaVideo


# Импортируем классы из наших модулей
from handlers.keyboards import Keyboards
from handlers.validators import Validators
from handlers.constans import CAKE_NAMES, SIZES, LOGISTICS


router = Router()
db = None


def setup_database(database):
    global db
    db = database


# Инициализируем экземпляры классов
kb = Keyboards()
validator = Validators()


# ======================= КОЛЛБЕК ОБРАБОТЧИКИ =======================

@router.callback_query(lambda c: c.data == "catalog")
async def catalog(callback: CallbackQuery):

    await callback.answer()

    items = await db.get_catalog()

    if not items:
        await callback.message.answer(
            "Каталог пока пуст 😢",
            reply_markup=kb.get_back_keyboard()
        )
        return

    await callback.message.answer("🛍 Каталог:")

    for item in items:
        text = f"{item['title']}\n\n{item['description']}"

        if item.get("file_id"):
            await callback.message.answer_photo(
                photo=item["file_id"],
                caption=text, parse_mode="HTML",
                reply_markup=kb.get_back_keyboard()
            )
        else:
            await callback.message.answer(
                text, parse_mode="HTML",
                reply_markup=kb.get_back_keyboard()
            )


@router.callback_query(lambda c: c.data == "view_works")
async def view_works(callback: CallbackQuery):
    await callback.answer("Вы выбрали посмотреть мои работы.")

    works = await db.get_works()

    if not works:
        await callback.message.answer("Пока нет работ 😢", reply_markup=kb.get_back_keyboard())
        return

    media = []

    for index, work in enumerate(works):

        caption = "📸 Мои работы" if index == 0 else None

        if work["media_type"] == "photo":
            media.append(
                InputMediaPhoto(
                    media=work["file_id"],
                    caption=caption
                )
            )

        elif work["media_type"] == "video":
            media.append(
                InputMediaVideo(
                    media=work["file_id"],
                    caption=caption
                )
            )

    for i in range(0, len(media), 10):
        await callback.message.answer_media_group(
            media=media[i:i + 10]
        )

    await callback.message.answer(
        "Здесь вы можете посмотреть мои работы.",
        reply_markup=kb.get_back_keyboard()
    )


@router.callback_query(lambda c: c.data == "reviews")
async def reviews(callback: CallbackQuery):
    await callback.answer()

    reviews = await db.get_reviews()

    if not reviews:
        await callback.message.answer(
            "Пока нет отзывов 😢",
            reply_markup=kb.get_back_keyboard()
        )
        return

    media = []

    for i, r in enumerate(reviews):

        file_id = r["file_id"]
        text = r["text"]

        if file_id:
            caption = text if text else None

            media.append(
                InputMediaPhoto(
                    media=file_id,
                    caption=caption if len(media) == 0 else None
                )
            )

    # отправка альбомами по 10 (лимит Telegram)
    for i in range(0, len(media), 10):
        await callback.message.answer_media_group(
            media=media[i:i + 10]
        )

    await callback.message.answer(
        """Отзывы клиентов 💬
Вы также можете написать отзыв мне в личные сообщения: @Sewwwqp)))""",
        reply_markup=kb.get_back_keyboard()
    )


@router.callback_query(lambda c: c.data == "contact_me")
async def contact_me(callback: CallbackQuery):
    await callback.answer("Вы выбрали написать мне.")
    await callback.message.answer("""Со мной можно связаться вот по этим контактам:
                                  
ТГ-аккаунт: @Sewwwqp
Страница Вконтакте: https://vk.com/polya_smi
Телеграмм-канал: https://t.me/tortsm
Сообщество Вконтакте: https://vk.com/club235221265

Буду рада помочь Вам!🤗""", reply_markup=kb.get_back_keyboard())


@router.callback_query(lambda c: c.data == "make_order")
async def make_order(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Вы выбрали сделать заказ.")
    await state.set_state(Form.fullname)
    await callback.message.answer("Давайте создадим заявку Вашего заказа. Для начала введите Ваше ФИО:", reply_markup=kb.get_back_keyboard())


@router.callback_query(lambda c: c.data == "back")
async def back(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Вы вернулись в главное меню.")
    await state.clear()
    await callback.message.answer("Главное меню:", reply_markup=kb.get_main_menu())


@router.callback_query(lambda c: c.data == "skip")
async def skip(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Вы пропустили этот шаг.")
    await state.update_data(
        media_type=None,
        media=None
    )
    await state.set_state(Form.additional_info)
    await callback.message.answer("Если у Вас есть дополнительная информация или пожелания, пожалуйста, напишите.")


@router.callback_query(lambda c: c.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    try:
        data = await state.get_data()

        if not data:
            await callback.message.answer("Ошибка: данные заявки пустые")
            return

        await db.add_order(
            telegram_id=callback.from_user.id,
            data=data
        )

        admin_id_1 = getenv("ADMIN_ID_1")
        admin_id_2 = getenv("ADMIN_ID_2")

        order_text = f"""
🆕 Новый заказ

ФИО: {data['fullname']}
Телефон: {data['phone_number']}
Аккаунт: {data['account']}

Торт: {data['cake']}
Размер: {data['size']}
Дата: {data['date_delivery']}
Доставка: {data['logistics']}

Дополнительная информация:
{data['additional_info']}
"""

        media_type = data.get("media_type")
        media = data.get("media")

        if media_type == "photo":
            await callback.bot.send_photo(
                chat_id=admin_id,
                photo=media,
                caption=order_text
            )

        elif media_type == "video":
            await callback.bot.send_video(
                chat_id=admin_id,
                video=media,
                caption=order_text
            )

        else:
            await callback.bot.send_message(
                chat_id=admin_id,
                text=order_text
            )

        await state.clear()

        await callback.message.answer(
            "Заказ принят! Я свяжусь с вами 😊",
            reply_markup=kb.get_back_keyboard()
        )

    except Exception as e:
        print("ERROR:", e)
        await callback.message.answer("Произошла ошибка при создании заказа")


@router.callback_query(lambda c: c.data == "edit_order")
async def edit_order(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Вы выбрали заполнить заявку заново.")
    await callback.message.answer("""Давайте начнем заново.
Введите Ваше ФИО:""", reply_markup=kb.get_back_keyboard())
    await state.set_state(Form.fullname)


@router.callback_query(Form.cake, lambda c: c.data.startswith("cake_"))
async def process_cake(callback: CallbackQuery, state: FSMContext):
    cake_choice = CAKE_NAMES[callback.data]
    await state.update_data(cake=cake_choice)

    await callback.answer()
    await state.set_state(Form.size)
    await callback.message.answer("Теперь выберите размер торта:", reply_markup=kb.get_size_choice())


@router.callback_query(Form.size, lambda c: c.data.startswith("size_"))
async def process_size(callback: CallbackQuery, state: FSMContext):
    size_choice = SIZES[callback.data]
    await state.update_data(size=size_choice)

    await callback.answer()
    await state.set_state(Form.date)
    await callback.message.answer("Выберите дату, к которой нужно приготовить торт:", reply_markup=await kb.get_calendar())


@router.callback_query(SimpleCalendarCallback.filter(), Form.date)
async def process_date(
    callback: CallbackQuery,
    callback_data: SimpleCalendarCallback,
    state: FSMContext
):
    selected, date_selected = await SimpleCalendar().process_selection(
        callback,
        callback_data
    )

    if not selected:
        return

    is_valid, message = validator.validate_date(date_selected)

    if not is_valid:
        await callback.answer(
            message,
            show_alert=True
        )

        await callback.message.answer(
            "Выберите дату не менее чем через 3 дня от текущей даты:",
            reply_markup=await kb.get_calendar()
        )
        return

    # 📅 формат даты
    formatted_date = date_selected.strftime("%d.%m.%Y")

    # 📌 проверка лимита бронирований (3/3)
    count = await db.count_orders_by_date(formatted_date)

    if count >= 3:
        await callback.answer(
            "Эта дата уже занята (3 из 3 заказов)",
            show_alert=True
        )

        await callback.message.answer(
            "Выберите дату в будущем:",
            reply_markup=await kb.get_calendar()
        )
        return

    # 💾 сохраняем дату
    await state.update_data(date_delivery=formatted_date)

    await state.set_state(Form.logistics)

    await callback.message.answer(
        "Выберите способ доставки:",
        reply_markup=kb.get_logistics_choice()
    )


@router.callback_query(Form.logistics, lambda c: c.data.startswith("logistics_"))
async def process_logistics(callback: CallbackQuery, state: FSMContext):
    logistics_choice = LOGISTICS[callback.data]
    await state.update_data(logistics=logistics_choice)

    await callback.answer()
    await state.set_state(Form.media)
    await callback.message.answer("Вы можете отправить фото или видео в качестве референса", reply_markup=kb.get_miss_keyboard())


# ======================= СООБЩЕНИЯ =======================

@router.message(Command("start"))
@router.message(F.text.lower() == "старт")
async def start(message: Message, state: FSMContext):

    await db.add_user(
        telegram_id=message.from_user.id,
        fullname=message.from_user.first_name,
        username=message.from_user.username
    )

    await message.answer(
        f"""<b>Привет, {message.from_user.first_name}!</b> 
Я <i>Poli</i>, новый телеграмм-бот

Зачем я нужен?
Отвечу просто — для удобства коммуникации и обратной связи)

Что здесь есть?
• каталог товаров
• мои работы
• ваши отзывы
• мои контакты
• и возможность сделать заказ прямо здесь

В общем, устраивайся уютно — я постараюсь быть полезным 😌""",
        parse_mode="HTML",
        reply_markup=kb.get_main_menu())


@router.message(Command("help"))
async def help(message: Message):
    await message.answer(
        "Список команд:\n\n"
        "/start - Запустить бота\n"
        "/help - Получить список команд\n", reply_markup=kb.get_back_keyboard())


@router.callback_query(lambda c: c.data == "about")
async def about_callback(callback: CallbackQuery):
    await callback.answer("Вы выбрали обо мне.")

    await callback.message.answer_photo(
        photo="AgACAgIAAxkBAAIJGmob31lGNiN9qux8qVYFTGuVK1RdAAI1HGsb1pfYSH2RxgvNHuh-AQADAgADeQADOwQ",
        caption="""Привет-привет! Я Полина. Пеку торты не по учебникам, а по любви💗✨
А этот бот — мой маленький помощник🤖
Первый раз испекла торт больше пяти лет назад — и затянуло😊🍰
На заказ работаю около двух лет, и за это время собрала не только навыки, но и искренние «спасибо».
🙏💕

Хочу, чтобы вкусных тортов в этом мире стало чуть больше
И именно ты можешь мне в этом помочь)🍰👩‍🍳""",
        reply_markup=kb.get_back_keyboard()
    )


@router.message(StateFilter(Form.fullname), F.text)
async def process_fullname(message: Message, state: FSMContext):
    is_valid, result = validator.validate_fullname(message.text)

    if not is_valid:
        await message.answer(result)
        return

    await state.update_data(fullname=message.text)
    await state.set_state(Form.phone_number)
    await message.answer("Теперь введите Ваш номер телефона:")


@router.message(StateFilter(Form.phone_number), F.text)
async def process_phone_number(message: Message, state: FSMContext):
    is_valid, result = validator.validate_phone(message.text)

    if not is_valid:
        await message.answer(result)
        return

    await state.update_data(phone_number=result)
    await state.set_state(Form.account)
    await message.answer("Теперь напишите ссылку на Ваш ВК/ТГ:")


@router.message(StateFilter(Form.account), F.text)
async def process_account(message: Message, state: FSMContext):
    is_valid, response = validator.validate_social_account(message.text)

    if not is_valid:
        await message.answer(response)
        return

    await state.update_data(account=message.text)
    await state.set_state(Form.cake)
    await message.answer("Теперь выберите торт:", reply_markup=kb.get_cake_choice())


@router.message(StateFilter(Form.media))
async def process_media(message: Message, state: FSMContext):
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
        await state.update_data(
            media_type=None,
            media=None
        )

    else:
        await message.answer("Отправьте фото или видео", reply_markup=kb.get_miss_keyboard())
        return

    await state.set_state(Form.additional_info)
    await message.answer("""Если у Вас есть дополнительная информация или пожелания, пожалуйста, напишите.
Если Вы выбрали доставку, пожалуйста, укажите адрес и время куда привезти заказ.""")


@router.message(StateFilter(Form.additional_info))
async def process_additional_info(message: Message, state: FSMContext):
    await state.update_data(additional_info=message.text)

    data = await state.get_data()
    media_type = data.get("media_type")

    if media_type == "photo":
        media_text = "Фото"
    elif media_type == "video":
        media_text = "Видео"
    else:
        media_text = "не прикреплено"

    fullname = data["fullname"]
    phone_number = data["phone_number"]
    account = data["account"]
    cake = data["cake"]
    size = data["size"]
    date = data["date_delivery"]
    logistics = data["logistics"]
    additional_info = data["additional_info"]

    await message.answer(f"""Проверьте созданную заявку:
ФИО: {fullname}
Номер телефона: {phone_number}
Аккаунт: {account}
Торт: {cake}
Размер: {size}
Дата: {date}
Способ доставки: {logistics}
Медиавложения: {media_text}
Дополнительная информация: {additional_info}""", reply_markup=kb.get_check_keyboard())


@router.message(F.photo)
async def get_photo_id(message: Message):
    file_id = message.photo[-1].file_id

    await message.answer(f"file_id:\n{file_id}")


@router.message(F.video)
async def get_video_id(message: Message):
    file_id = message.video.file_id

    await message.answer(f"file_id:\n{file_id}")


@router.message()
async def unknown_message(message: Message, state: FSMContext):

    current_state = await state.get_state()

    # Если FSM активен — ничего не делаем
    if current_state:
        return

    await message.answer(
        "Извините, я не понимаю эту команду.\n"
        "Напишите /help для списка команд."
    )
