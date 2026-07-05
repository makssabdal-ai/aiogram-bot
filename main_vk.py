import asyncio
from os import getenv
import sys

from dotenv import load_dotenv

from database.db import Database
from vk_bot.bot import VKCakeBot
from vk_bot.client import VKApiError, VKClient


load_dotenv(override=True)

VK_GROUP_TOKEN = getenv("VK_GROUP_TOKEN")
VK_GROUP_ID = getenv("VK_GROUP_ID")
DATABASE_URL = getenv("DATABASE_URL")
BOT_TOKEN = getenv("BOT_TOKEN") or getenv("BOT_TOKEN ")
ADMIN_IDS = getenv("ADMIN_IDS") or getenv("ADMIN_IDS ")

if not VK_GROUP_TOKEN or not VK_GROUP_ID or not DATABASE_URL:
    print("Критическая ошибка: VK_GROUP_TOKEN, VK_GROUP_ID или DATABASE_URL не найдены в .env")
    sys.exit(1)

if not BOT_TOKEN or not ADMIN_IDS:
    print("Критическая ошибка: BOT_TOKEN или ADMIN_IDS не найдены. VK-бот не сможет отправлять заказы администраторам в Telegram.")
    sys.exit(1)


def parse_group_id(value: str) -> int:
    value = value.strip().rstrip("/")
    if value.isdigit():
        return int(value)
    marker = "club"
    if marker in value:
        group_id = value.rsplit(marker, 1)[1]
        if group_id.isdigit():
            return int(group_id)
    raise ValueError("VK_GROUP_ID должен быть числом, club123456 или ссылкой вида https://vk.com/club123456")


async def main():
    try:
        group_id = parse_group_id(VK_GROUP_ID)
    except ValueError as exc:
        print(f"Критическая ошибка: {exc}")
        sys.exit(1)

    db = Database(DATABASE_URL)
    print("[VK DB] Подключение к базе данных...")
    await db.connect()
    await db.init_tables()

    client = VKClient(token=VK_GROUP_TOKEN, group_id=group_id)
    bot = VKCakeBot(client=client, db=db)

    print("[VK] Запуск VK-бота в режиме Long Poll...")
    try:
        async with client:
            while True:
                updates = await client.poll()
                for update in updates:
                    try:
                        await bot.handle_update(update)
                    except Exception as exc:
                        print(f"[VK ERROR] Failed to handle update: {exc}")
    except VKApiError as exc:
        print(f"[VK ERROR] {exc}")
        print("Проверьте, что VK_GROUP_TOKEN - это токен сообщества с доступом к сообщениям.")
        print("В настройках сообщества VK также должен быть включен Long Poll API и события входящих сообщений.")
    finally:
        await db.close()
        await client.close()
        print("[VK] Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
