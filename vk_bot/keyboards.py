import json
import re
from datetime import date, timedelta
from html import unescape


def clean_label(text: str) -> str:
    return unescape(re.sub(r"<[^>]*>", "", text or "")).strip()


def wrap_label(text: str, limit: int = 24) -> str:
    text = clean_label(text)
    if len(text) <= limit or "\n" in text:
        return text

    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + len(word) + 1 > limit:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return "\n".join(lines[:2])


def _button(label: str, cmd: str, color: str = "secondary") -> dict:
    return {
        "action": {
            "type": "text",
            "label": wrap_label(label),
            "payload": json.dumps({"cmd": cmd}, ensure_ascii=False),
        },
        "color": color,
    }


def keyboard(rows: list[list[dict]], inline: bool = True, one_time: bool = False) -> str:
    return json.dumps(
        {
            "one_time": one_time,
            "inline": inline,
            "buttons": rows,
        },
        ensure_ascii=False,
    )


def main_menu() -> str:
    return keyboard(
        [
            [_button("Каталог товаров 🛍", "catalog")],
            [_button("Мои работы 📸", "view_works")],
            [_button("Отзывы 💬", "reviews")],
            [_button("Написать мне ✉️", "contact_me")],
            [_button("Обо мне 👩‍🍳", "about"), _button("Согласие", "personal_data_info")],
            [_button("Сделать заказ ✨", "make_order", "positive")],
        ]
    )


def personal_data_consent_menu() -> str:
    return keyboard([[_button("Согласен(на)", "personal_data_consent_accept", "positive")]])


def back_menu() -> str:
    return keyboard([[_button("В главное меню", "back", "primary")]])


def skip_menu() -> str:
    return keyboard([[_button("Пропустить шаг", "skip", "primary")]], inline=True)


def paged_rows(buttons: list[dict], page: int, page_size: int = 5, back_cmd: str = "back") -> list[list[dict]]:
    page = max(page, 0)
    start = page * page_size
    chunk = buttons[start:start + page_size]
    rows = [[button] for button in chunk]

    nav = []
    if page > 0:
        nav.append(_button("Назад", f"{back_cmd}:{page - 1}"))
    if start + page_size < len(buttons):
        nav.append(_button("Еще", f"{back_cmd}:{page + 1}", "primary"))
    if nav:
        rows.append(nav)
    return rows


def catalog_menu(items, page: int = 0) -> str:
    product_buttons = [_button(str(item["title"]), f"product:{item['id']}", "primary") for item in items]
    rows = paged_rows(product_buttons, page, page_size=4, back_cmd="catalog_page")
    rows.append([_button("⬅️ В главное меню", "back")])
    return keyboard(rows)


def product_back_menu() -> str:
    return keyboard([[_button("Назад в каталог", "catalog", "primary")]])


def works_menu(has_more: bool) -> str:
    rows = []
    if has_more:
        rows.append([_button("Показать еще", "works_more", "primary")])
    rows.append([_button("В главное меню", "back")])
    return keyboard(rows)


def cake_menu(page: int = 0) -> str:
    buttons = [
        _button("Банан-карамель", "cake_1"),
        _button("Баунти", "cake_2"),
        _button("Молочная девочка", "cake_3"),
        _button("Красный бархат", "cake_4"),
        _button("Фисташка-малина", "cake_5"),
        _button("Медовик", "cake_6"),
        _button("Сникерс", "cake_7"),
        _button("Черный лес", "cake_8"),
    ]
    return keyboard(paged_rows(buttons, page, back_cmd="cake_page"), inline=True)


def size_menu() -> str:
    return keyboard(
        [
            [_button("Стандарт 18 см", "size_standard")],
            [_button("Бенто 14 см", "size_bento")],
        ],
        inline=True,
    )


def logistics_menu() -> str:
    return keyboard(
        [
            [_button("Самовывоз", "logistics_pickup")],
            [_button("Доставка", "logistics_delivery")],
        ],
        inline=True,
    )


def check_menu() -> str:
    return keyboard(
        [
            [_button("Все верно", "confirm_order", "positive")],
            [_button("Заново", "edit_order", "negative")],
        ],
        inline=True,
    )


def date_menu(offset: int = 0) -> str:
    start = date.today() + timedelta(days=3 + offset)
    days = [start + timedelta(days=index) for index in range(8)]
    rows = []
    for index in range(0, len(days), 2):
        rows.append([
            _button(day.strftime("%d.%m"), f"date_pick:{day.strftime('%d.%m.%Y')}", "secondary")
            for day in days[index:index + 2]
        ])
    rows.append([
        _button("← Раньше", f"date_page:{max(0, offset - 8)}"),
        _button("Позже →", f"date_page:{offset + 8}", "primary"),
    ])
    return keyboard(rows)
