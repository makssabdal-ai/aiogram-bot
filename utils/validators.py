import re
from datetime import date, timedelta


class Validators:
    """Утилитарные статические методы для валидации вводимых пользователем данных"""

    @staticmethod
    def validate_phone(phone: str) -> tuple[bool, str]:
        # Удаляем все символы, кроме цифр
        phone = re.sub(r'\D', '', phone)

        # Если ввели 10 цифр и начинается с 9 (например, 9991234567)
        if len(phone) == 10 and phone.startswith('9'):
            phone = '8' + phone
        # Если ввели 11 цифр и начинается с 7 (например, 79991234567)
        elif len(phone) == 11 and phone.startswith('7'):
            phone = '8' + phone[1:]
        # Если ввели 11 цифр и начинается с 8 — оставляем как есть
        elif len(phone) == 11 and phone.startswith('8'):
            pass
        else:
            return False, "❌ Неверный формат номера. Введите 11 цифр телефона (например, 89991234567 или +79991234567):"

        return True, phone

    @staticmethod
    def validate_social_account(url: str) -> tuple[bool, str]:
        url = url.strip()
        telegram_patterns = [
            r'^@[\w]{3,32}$',
            r'^https?://t\.me/[\w]{3,32}$',
            r'^https?://telegram\.me/[\w]{3,32}$'
        ]
        vk_patterns = [
            r'^https?://vk\.com/[\w.]+$',
            r'^https?://www\.vk\.com/[\w.]+$',
            r'^vk\.com/[\w.]+$'
        ]

        for pattern in telegram_patterns + vk_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True, url

        return False, "❌ Ссылка некорректна. Отправьте юзернейм вида @username или ссылку на страницу VK:"

    @staticmethod
    def validate_date(selected_date) -> tuple[bool, str]:
        if hasattr(selected_date, 'date'):
            selected_date = selected_date.date()

        today = date.today()
        min_date = today + timedelta(days=3)

        if selected_date < today:
            return False, "Вы выбрали дату в прошлом!"
        if selected_date < min_date:
            return False, "Заказ нужно оформлять минимум за 3 дня до события!"
        return True, "Ок"

    @staticmethod
    def validate_fullname(fullname: str) -> tuple[bool, str]:
        fullname = fullname.strip()

        # 1. Проверка длины
        if len(fullname) < 3:
            return False, "❌ Имя слишком короткое. Введите корректное ФИО:"

        # 2. Проверка на наличие цифр и спецсимволов
        # Шаблон: только русские буквы (А-Я, а-я), пробелы (\s) и тире (\-)
        # ^ - начало строки, $ - конец строки, + означает "один или более"
        if not re.match(r'^[А-Яа-яЁё\s\-]+$', fullname):
            return False, "❌ Имя содержит недопустимые символы. Используйте только буквы:"

        return True, fullname
