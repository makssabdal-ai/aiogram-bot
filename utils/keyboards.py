import re
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram_calendar import SimpleCalendar

from utils.consent import CONSENT_CALLBACK


class Keyboards:
    """Класс-фабрика генерации инлайн-клавиатур интерфейса бота"""

    @staticmethod
    def _clean_html(text: str) -> str:
        """Вспомогательный метод очистки HTML-тегов для текста на кнопках"""
        if not text:
            return ""
        return re.sub(r'<[^>]*>', '', text)

    @staticmethod
    def get_main_menu() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Каталог товаров 🛍", callback_data="catalog"),
                    InlineKeyboardButton(
                        text="Мои работы 📸", callback_data="view_works")
                ],
                [
                    InlineKeyboardButton(
                        text="Отзывы 💬", callback_data="reviews"),
                    InlineKeyboardButton(
                        text="Написать мне ✉️", callback_data="contact_me")
                ],
                [
                    InlineKeyboardButton(
                        text="Обо мне 👩‍🍳", callback_data="about")
                ],
                [
                    InlineKeyboardButton(
                        text="✨ Сделать заказ ✨", callback_data="make_order")
                ]
            ]
        )

    @staticmethod
    def get_personal_data_consent_keyboard() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="Я прочитал(а) и согласен(на)",
                    callback_data=CONSENT_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ В главное меню",
                    callback_data="back",
                )
            ]]
        )

    @staticmethod
    def get_catalog_keyboard(items) -> InlineKeyboardMarkup:
        # Создаем кнопки для товаров, предварительно очистив их названия от HTML-тегов
        buttons = [
            [InlineKeyboardButton(text=Keyboards._clean_html(
                item["title"]), callback_data=f"product:{item['id']}")]
            for item in items
        ]
        # Добавляем кнопку возврата в главное меню в самый конец списка товаров
        buttons.append([InlineKeyboardButton(
            text="⬅️ В главное меню", callback_data="back")])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def get_product_back_keyboard() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="⬅️ Назад в каталог", callback_data="catalog")]
            ]
        )

    @staticmethod
    def get_miss_keyboard() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(
                text="Пропустить шаг ➡️", callback_data="skip")]]
        )

    @staticmethod
    def get_back_keyboard() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(
                text="⬅️ В главное меню", callback_data="back")]]
        )

    @staticmethod
    def get_cake_choice() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Банан-карамель 🍌", callback_data="cake_1"),
                    InlineKeyboardButton(
                        text="Баунти 🥥", callback_data="cake_2")
                ],
                [
                    InlineKeyboardButton(
                        text="Молочная девочка 🥛", callback_data="cake_3"),
                    InlineKeyboardButton(
                        text="Красный бархат ❤️", callback_data="cake_4")
                ],
                [
                    InlineKeyboardButton(
                        text="Фисташка-малина 🥑", callback_data="cake_5"),
                    InlineKeyboardButton(
                        text="Медовик 🍯", callback_data="cake_6")
                ],
                [
                    InlineKeyboardButton(
                        text="Сникерс 🍫", callback_data="cake_7"),
                    InlineKeyboardButton(
                        text="Черный лес 🍒", callback_data="cake_8")
                ]
            ]
        )

    @staticmethod
    def get_size_choice() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Стандарт (18см)", callback_data="size_standard"),
                    InlineKeyboardButton(
                        text="Бенто (14см)", callback_data="size_bento")
                ]
            ]
        )

    @staticmethod
    async def get_calendar():
        return await SimpleCalendar().start_calendar()

    @staticmethod
    def get_logistics_choice() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Самовывоз 📦",
                                      callback_data="logistics_pickup")],
                [InlineKeyboardButton(
                    text="Доставка (доплата) 🚗", callback_data="logistics_delivery")],
            ]
        )

    @staticmethod
    def get_check_keyboard() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Все верно ✅", callback_data="confirm_order"),
                    InlineKeyboardButton(
                        text="Заново 🔄", callback_data="edit_order")
                ]
            ]
        )

    @staticmethod
    def get_works_keyboard(has_more: bool) -> InlineKeyboardMarkup:
        buttons = []
        if has_more:
            buttons.append([InlineKeyboardButton(
                text="Показать еще 📸", callback_data="more_works")])
        buttons.append([InlineKeyboardButton(
            text="⬅️ В главное меню", callback_data="back")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)
