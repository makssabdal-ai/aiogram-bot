"""Импорт VK-медиа: python -m scripts.import_vk_media [--apply]."""

import argparse
import asyncio
import json
import re
from datetime import datetime, timedelta
from html import unescape
from os import getenv
from pathlib import Path

from dotenv import load_dotenv

from database.db import Database


def normalize_title(title):
    plain = unescape(re.sub(r"<[^>]+>", "", title))
    return " ".join(plain.casefold().replace("ё", "е").split())


def media_type(file_id):
    match = re.fullmatch(r"(photo|video)-?\d+_\d+(?:_[A-Za-z0-9]+)?", file_id)
    if not match:
        raise ValueError("Invalid VK attachment ID")
    return match[1]


async def import_media(conn, payload, apply=False):
    # Проверка и запись выполняются под одной блокировкой и в одной транзакции.
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(724019301)")
        cards = await conn.fetch("SELECT id, title FROM catalog WHERE title IS NOT NULL")
        targets = []
        for item in payload["catalog"]:
            matches = [c for c in cards if normalize_title(c["title"]) == normalize_title(item["title"])]
            if len(matches) != 1:
                raise ValueError(f"Expected exactly one catalog card: {item['title']}")
            targets.append((matches[0]["id"], item["vk_file_id"], media_type(item["vk_file_id"])))
        if len({row[0] for row in targets}) != len(targets):
            raise ValueError("Duplicate catalog target")

        summary = {"catalog_matched": len(targets)}
        rows_to_insert = {}
        for table in ("reviews", "works"):
            unique = list(dict.fromkeys(payload[table]))
            for file_id in unique:
                media_type(file_id)
            existing = await conn.fetch(f"SELECT vk_file_id FROM {table} WHERE vk_file_id IS NOT NULL")
            known = {r["vk_file_id"] for r in existing}
            rows_to_insert[table] = [v for v in unique if v not in known]
            summary[table] = {"unique": len(unique), "new": len(rows_to_insert[table]),
                              "duplicates_in_input": len(payload[table]) - len(unique)}

        if apply:
            await conn.executemany(
                "UPDATE catalog SET vk_file_id=$2, vk_media_type=$3 WHERE id=$1", targets)
            now = datetime.now()
            for table in ("reviews", "works"):
                # Только новые VK-строки; Telegram file_id и подписи не затрагиваются.
                await conn.executemany(
                    f"INSERT INTO {table} (vk_file_id, vk_media_type, created_at) VALUES ($1,$2,$3)",
                    [(v, media_type(v), now - timedelta(microseconds=i))
                     for i, v in enumerate(rows_to_insert[table])])
                # Тип восстанавливается также у ранее импортированных записей.
                await conn.executemany(
                    f"UPDATE {table} SET vk_media_type=$2 WHERE vk_file_id=$1",
                    [(v, media_type(v)) for v in dict.fromkeys(payload[table])])
        return summary


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/vk_media.json"))
    parser.add_argument("--apply", action="store_true", help="Записать изменения; по умолчанию только проверка")
    args = parser.parse_args()
    load_dotenv(".env", encoding="utf-8-sig")
    payload = json.loads(args.data.read_text(encoding="utf-8"))
    db = Database(getenv("DATABASE_URL"))
    await db.connect()
    try:
        if args.apply:
            await db.init_tables()
        async with db.pool.acquire() as conn:
            result = await import_media(conn, payload, apply=args.apply)
        print(json.dumps({"applied": args.apply, **result}, ensure_ascii=False, indent=2))
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
