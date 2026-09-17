import os
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlsplit

import asyncpg

from database.db import Database
from scripts.import_vk_media import import_media


class IdentityValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_or_ambiguous_identity_rejected_before_sql(self):
        db = Database("unused")
        for kwargs in ({}, {"telegram_id": 1, "vk_id": 1}, {"vk_id": -1}, {"telegram_id": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                await db.add_user(**kwargs)

    async def test_vk_bot_passes_positive_vk_id(self):
        from vk_bot.bot import VKCakeBot
        db = MagicMock()
        db.add_user = AsyncMock()
        db.has_personal_data_consent = AsyncMock(return_value=False)
        bot = VKCakeBot(MagicMock(), db)
        bot.get_vk_user_name = AsyncMock(return_value="Test")
        bot.send_vk = AsyncMock()
        await bot.ensure_personal_data_consent(1, 123)
        db.has_personal_data_consent.assert_awaited_once_with(vk_id=123)
        self.assertEqual(db.add_user.call_args.kwargs["vk_id"], 123)
        self.assertNotIn("telegram_id", db.add_user.call_args.kwargs)


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "TEST_DATABASE_URL is not set")
class PlatformDatabaseTests(unittest.IsolatedAsyncioTestCase):
    """Каждый тест создаёт и удаляет отдельную схему; public не изменяется."""

    async def asyncSetUp(self):
        dsn = os.environ["TEST_DATABASE_URL"]
        ssl = False if urlsplit(dsn).hostname in ("localhost", "127.0.0.1", "::1") else "require"
        self.admin = await asyncpg.connect(dsn, ssl=ssl)
        self.schema = "test_vk_" + uuid.uuid4().hex
        await self.admin.execute(f'CREATE SCHEMA "{self.schema}"')
        self.addAsyncCleanup(self.cleanup_schema)
        self.db = Database(dsn)
        self.db.pool = await asyncpg.create_pool(
            dsn, ssl=ssl, min_size=1, max_size=2,
            server_settings={"search_path": self.schema})
        self.addAsyncCleanup(self.db.close)
        await self.db.init_tables()

    async def cleanup_schema(self):
        await self.admin.execute(f'DROP SCHEMA "{self.schema}" CASCADE')
        await self.admin.close()

    async def test_same_numeric_ids_have_separate_users_consent_and_orders(self):
        await self.db.add_user(123, "Telegram")
        await self.db.add_user(vk_id=123, fullname="VK")
        await self.db.set_personal_data_consent(vk_id=123, platform="vk", document="v1")
        self.assertFalse(await self.db.has_personal_data_consent(123))
        self.assertTrue(await self.db.has_personal_data_consent(vk_id=123))
        await self.db.add_order(123, {"media": "telegram_file"})
        await self.db.add_order(vk_id=123, data={"media": "photo123_456_key", "media_type": "photo"})
        async with self.db.pool.acquire() as c:
            self.assertEqual(await c.fetchval("SELECT count(*) FROM users"), 2)
            tg = await c.fetchrow("SELECT * FROM orders WHERE user_id=123")
            vk = await c.fetchrow("SELECT * FROM orders WHERE vk_id=123")
            self.assertIsNone(tg["vk_id"])
            self.assertIsNone(tg["vk_file_id"])
            self.assertEqual(tg["media"], "telegram_file")
            self.assertIsNone(vk["user_id"])
            self.assertIsNone(vk["media"])
            self.assertEqual(vk["vk_file_id"], "photo123_456_key")
            self.assertEqual(vk["vk_media_type"], "photo")

    async def test_legacy_migration_is_repeatable_and_preserves_consent(self):
        async with self.db.pool.acquire() as c:
            await c.execute("INSERT INTO users (telegram_id, personal_data_consent) VALUES (-123, TRUE)")
            await c.execute("INSERT INTO orders (user_id, media) VALUES (-123, 'video123_456_key')")
            await c.execute("INSERT INTO reviews (user_id, text) VALUES (-123, 'Review')")
        await self.db.init_tables()
        await self.db.init_tables()
        self.assertTrue(await self.db.has_personal_data_consent(vk_id=123))
        async with self.db.pool.acquire() as c:
            user = await c.fetchrow("SELECT * FROM users")
            self.assertIsNone(user["telegram_id"])
            self.assertEqual(user["vk_id"], 123)
            order = await c.fetchrow("SELECT * FROM orders")
            self.assertIsNone(order["user_id"])
            self.assertIsNone(order["media"])
            self.assertEqual(order["vk_file_id"], "video123_456_key")
            self.assertEqual(order["vk_media_type"], "video")
            review = await c.fetchrow("SELECT * FROM reviews")
            self.assertIsNone(review["user_id"])
            self.assertEqual(review["vk_id"], 123)

    async def test_import_matches_titles_preserves_telegram_and_deduplicates(self):
        async with self.db.pool.acquire() as c:
            await c.execute("INSERT INTO catalog (title,file_id) VALUES ('<b>Чёрный лес</b>','tg_catalog')")
            await c.execute("INSERT INTO reviews (file_id) VALUES ('tg_review')")
            await c.execute("INSERT INTO works (file_id,media_type) VALUES ('tg_work','photo')")
            payload = {"catalog": [{"title": "черный лес", "vk_file_id": "photo1_2_key"}],
                       "reviews": ["photo1_3_key", "photo1_3_key"], "works": ["video1_4_key"]}
            await import_media(c, payload)
            self.assertIsNone(await c.fetchval("SELECT vk_file_id FROM catalog"))
            result = await import_media(c, payload, apply=True)
            self.assertEqual(result["reviews"]["duplicates_in_input"], 1)
            again = await import_media(c, payload, apply=True)
            self.assertEqual(again["works"]["new"], 0)
            self.assertEqual(await c.fetchval("SELECT file_id FROM catalog"), "tg_catalog")
            self.assertEqual(await c.fetchval("SELECT vk_file_id FROM catalog"), "photo1_2_key")
            self.assertEqual(await c.fetchval("SELECT count(*) FROM reviews"), 2)
            self.assertEqual(await c.fetchval("SELECT count(*) FROM works"), 2)
            bad = {**payload, "catalog": [{"title": "Missing", "vk_file_id": "photo1_9_key"}]}
            with self.assertRaises(ValueError):
                await import_media(c, bad, apply=True)
            self.assertEqual(await c.fetchval("SELECT vk_file_id FROM catalog"), "photo1_2_key")
