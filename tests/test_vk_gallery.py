import unittest
from unittest.mock import AsyncMock, MagicMock

from vk_bot.bot import VKCakeBot
from vk_bot.client import VKApiError, VKClient


class GalleryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client.send_message = AsyncMock()
        self.db = MagicMock()
        self.bot = VKCakeBot(self.client, self.db)

    async def test_pages_have_no_gaps_and_last_page_has_no_more_button(self):
        self.db.get_works = AsyncMock(return_value=[
            {"vk_file_id": f"photo1_{i}_key"} for i in range(1, 24)])
        for _ in range(3):
            await self.bot.show_works_chunk(1, 1)
        calls = self.client.send_message.call_args_list
        self.assertEqual([len(c.kwargs["attachment"].split(",")) for c in calls], [10, 10, 3])
        all_files = [v for c in calls for v in c.kwargs["attachment"].split(",")]
        self.assertEqual(all_files, [f"photo1_{i}_key" for i in range(1, 24)])
        self.assertEqual(self.bot.works_offsets[1], 23)
        self.assertNotIn("works_more", calls[-1].kwargs["keyboard"])

    async def test_failed_page_is_retried_without_advancing_or_emoji_fallback(self):
        self.db.get_works = AsyncMock(return_value=[{"vk_file_id": "photo1_2_key"}])
        self.client.send_message.side_effect = [VKApiError("invalid attachment"), None, None]
        await self.bot.show_works_chunk(1, 1)
        self.assertEqual(self.bot.works_offsets.get(1, 0), 0)
        self.assertEqual(self.client.send_message.call_count, 2)
        await self.bot.show_works_chunk(1, 1)
        self.assertEqual(self.bot.works_offsets[1], 1)
        self.assertEqual(self.client.send_message.call_args.kwargs["attachment"], "photo1_2_key")

    async def test_reviews_send_two_nonempty_batches(self):
        self.db.get_reviews = AsyncMock(return_value=[
            {"vk_file_id": f"photo1_{i}_key"} for i in range(16)])
        await self.bot.show_reviews(1)
        calls = self.client.send_message.call_args_list
        self.assertEqual([len(c.kwargs["attachment"].split(",")) for c in calls], [10, 6])
        self.assertTrue(all(c.kwargs["text"] for c in calls))
        self.assertIsNotNone(calls[-1].kwargs["keyboard"])

    async def test_reviews_failure_leaves_navigation(self):
        self.db.get_reviews = AsyncMock(return_value=[{"vk_file_id": "photo1_2_key"}])
        self.client.send_message.side_effect = [VKApiError("invalid attachment"), None]
        await self.bot.show_reviews(1)
        self.assertIsNone(self.client.send_message.call_args.kwargs["attachment"])
        self.assertIsNotNone(self.client.send_message.call_args.kwargs["keyboard"])


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_silently_dropped_attachment_is_not_success(self):
        client = VKClient("unused", 1)
        client.api = AsyncMock(side_effect=[123, {"items": [{"attachments": []}]}])
        with self.assertRaises(VKApiError):
            await client.send_message(1, "Photo", attachment="photo1_2_key")

    async def test_delivered_media_types_are_verified(self):
        client = VKClient("unused", 1)
        client.api = AsyncMock(side_effect=[123, {"items": [{"attachments": [
            {"type": "photo", "photo": {"owner_id": 1, "id": 2}}
        ]}]}])
        self.assertEqual(await client.send_message(1, "Photo", attachment="photo1_2_key"), 123)
        client.api.assert_any_await("messages.getById", message_ids=123)

    async def test_vk_photo_copy_with_different_identity_is_accepted(self):
        client = VKClient("unused", 1)
        client.api = AsyncMock(side_effect=[123, {"items": [{"attachments": [
            {"type": "photo", "photo": {"owner_id": -99, "id": 888}}
        ]}]}])
        self.assertEqual(await client.send_message(1, "Photo", attachment="photo1_2_key"), 123)

    async def test_wrong_media_type_is_rejected(self):
        client = VKClient("unused", 1)
        client.api = AsyncMock(side_effect=[123, {"items": [{"attachments": [
            {"type": "video", "video": {"owner_id": 1, "id": 2}}
        ]}]}])
        with self.assertRaises(VKApiError):
            await client.send_message(1, "Photo", attachment="photo1_2_key")
