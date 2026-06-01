import asyncio
from os import getenv
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from database.db import Database
from handlers import register_all_handlers

# Загружаем переменные из .env файла
load_dotenv()

TOKEN = getenv("BOT_TOKEN")
DATABASE_URL = getenv("DATABASE_URL")

if not TOKEN or not DATABASE_URL:
    print("Критическая ошибка: Переменные BOT_TOKEN или DATABASE_URL не найдены в .env")
    sys.exit(1)


async def main():
    print("[INFO] Запуск бота...")

    # Инициализация базы данных
    db = Database(DATABASE_URL)
    print("[DB] Подключение к базе данных...")
    await db.connect()

    print("[DB] Инициализация таблиц...")
    await db.init_tables()

    # Инициализация бота и диспетчера
    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    dp = Dispatcher()

    # Передаем объект базы данных в workflow_data диспетчера,
    # чтобы иметь к нему доступ во всех хэндлерах через аргументы функций
    dp["db"] = db

    # Регистрируем все обработчики (роутеры)
    register_all_handlers(dp)

    print("[INFO] Бот успешно запущен в режиме Polling.")

    try:
        # Запускаем получение обновлений
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            timeout=60
        )
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        # Гарантированное закрытие сессий при остановке
        await db.close()
        await bot.session.close()
        print("[INFO] Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
