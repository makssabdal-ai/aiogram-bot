from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto, InputMediaVideo, Message
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from forms.user import Form

from database.db import Database
from utils.keyboards import Keyboards

router = Router()


@router.callback_query(F.data == "catalog")
async def callback_catalog(callback: CallbackQuery, db: Database):
    """Отображение каталога товаров"""
    await callback.answer()
    items = await db.get_catalog()

    if not items:
        # Если в базе нет товаров
        text_empty = "Каталог пока пуст 😢"
        try:
            await callback.message.edit_text(
                text=text_empty,
                reply_markup=Keyboards.get_back_keyboard(),
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            # Если предыдущее сообщение содержало фото/видео, edit_text упадет
            await callback.message.delete()
            await callback.message.answer(
                text=text_empty,
                reply_markup=Keyboards.get_back_keyboard(),
                parse_mode="HTML"
            )
        return

    # Формируем текст каталога
    catalog_text = "🛍 <b>Каталог товаров:</b>\nВыберите интересующую позицию:"
    reply_markup = Keyboards.get_catalog_keyboard(items)

    try:
        # Пробуем изменить текст текущего сообщения (работает, если не было фото)
        await callback.message.edit_text(
            text=catalog_text,
            reply_markup=reply_markup,
            parse_mode="HTML"  # Исправлено: теперь HTML-теги в названии/описании будут работать!
        )
    except TelegramBadRequest:
        # Защита от багов Telegram: если в сообщении было фото, удаляем его и отправляем текстом
        await callback.message.delete()
        await callback.message.answer(
            text=catalog_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("product:"))
async def callback_product_detail(callback: CallbackQuery, db: Database):
    """Просмотр конкретного товара из каталога"""
    await callback.answer()
    product_id = int(callback.data.split(":")[1])
    item = await db.get_product(product_id)

    if not item:
        await callback.message.answer("Товар не найден.")
        return

    # Поддерживаем HTML в описании карточки товара
    text = f"<b>{item['title']}</b>\n\n{item['description']}"
    reply_markup = Keyboards.get_product_back_keyboard()

    if item.get("file_id"):
        # Если у товара прикреплено изображение
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=item["file_id"],
                    caption=text,
                    parse_mode="HTML"
                ),
                reply_markup=reply_markup
            )
        except TelegramBadRequest:
            # Если до этого было чисто текстовое сообщение меню, edit_media не сработает.
            # В таком случае удаляем старое текстовое и отправляем новое с фото.
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=item["file_id"],
                caption=text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
    else:
        # Если у товара нет картинки — выводим только текст
        try:
            await callback.message.edit_text(
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer(
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )


# Добавляем новое состояние прямо в класс Form, если вы еще этого не сделали:
# Внутри вашего файла forms/user.py должна быть строчка: viewing_works = State()

@router.callback_query(F.data == "view_works")
async def callback_view_works(callback: CallbackQuery, state: FSMContext, db: Database):
    """Первоначальный запуск просмотра галереи готовых работ порциями"""
    await callback.answer("Загружаю портфолио...")

    works = await db.get_works()
    if not works:
        await callback.message.answer(
            text="Пока нет доступных работ 😢",
            reply_markup=Keyboards.get_back_keyboard()
        )
        return

    # Переводим пользователя в состояние просмотра портфолио и ставим указатель на 0
    await state.set_state(Form.viewing_works)
    await state.update_data(works_offset=0)

    # Отправляем самую первую пачку (первые 10 штук)
    await send_works_chunk(callback.message, works, offset=0, state=state)


@router.callback_query(Form.viewing_works, F.data == "more_works")
async def callback_more_works(callback: CallbackQuery, state: FSMContext, db: Database):
    """Обработка нажатия на кнопку 'Показать еще'"""
    await callback.answer("Загружаю еще...")

    # Удаляем сообщение с кнопками старой группы, чтобы чат выглядел чистым
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Берем текущий сдвиг (оффсет) из памяти бота
    user_data = await state.get_data()
    offset = user_data.get("works_offset", 0)

    works = await db.get_works()

    # Отправляем следующую пачку
    await send_works_chunk(callback.message, works, offset=offset, state=state)


async def send_works_chunk(message: Message, works: list, offset: int, state: FSMContext):
    """Вспомогательная функция, которая режет список работ и отправляет по 10 штук"""
    limit = 10
    chunk = works[offset:offset + limit]

    media = []
    for index, work in enumerate(chunk):
        # Красивую подпись ставим только к самой первой фотографии в альбоме
        caption = "📸 Наши готовые работы" if index == 0 and offset == 0 else None

        if work["media_type"] == "photo":
            media.append(InputMediaPhoto(
                media=work["file_id"], caption=caption))
        elif work["media_type"] == "video":
            media.append(InputMediaVideo(
                media=work["file_id"], caption=caption))

    if media:
        await message.answer_media_group(media=media)

    # Высчитываем новый оффсет для следующего шага
    new_offset = offset + limit
    has_more = new_offset < len(works)

    # Записываем обновленный шаг в память FSM
    await state.update_data(works_offset=new_offset)

    # Отправляем меню управления под альбомом
    if has_more:
        await message.answer(
            text=f"Показано {min(new_offset, len(works))} из {len(works)}. Хотите посмотреть еще?",
            reply_markup=Keyboards.get_works_keyboard(has_more=True)
        )
    else:
        await message.answer(
            text="✨ Вы посмотрели все доступные работы!",
            reply_markup=Keyboards.get_works_keyboard(has_more=False)
        )


@router.callback_query(F.data == "reviews")
async def callback_reviews(callback: CallbackQuery, db: Database):
    """Просмотр отзывов клиентов"""
    await callback.answer()
    reviews_list = await db.get_reviews()

    if not reviews_list:
        await callback.message.answer(
            text="Пока нет отзывов 😢",
            reply_markup=Keyboards.get_back_keyboard()
        )
        return

    media = []
    for r in reviews_list:
        file_id = r["file_id"]
        text = r["text"]

        if file_id:
            caption = text if text else None
            media.append(InputMediaPhoto(
                media=file_id, caption=caption if len(media) == 0 else None))

    for i in range(0, len(media), 10):
        await callback.message.answer_media_group(media=media[i:i + 10])

    await callback.message.answer(
        text="Отзывы клиентов 💬\n\nВы также можете написать отзыв мне в личные сообщения: @Sewwwqp)))",
        reply_markup=Keyboards.get_back_keyboard()
    )
