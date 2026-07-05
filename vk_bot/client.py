import asyncio
import secrets
from typing import Any

import aiohttp


class VKApiError(RuntimeError):
    pass


class VKClient:
    API_URL = "https://api.vk.com/method"
    API_VERSION = "5.199"

    def __init__(self, token: str, group_id: int):
        self.token = token
        self.group_id = group_id
        self.session: aiohttp.ClientSession | None = None
        self.server: str | None = None
        self.key: str | None = None
        self.ts: str | None = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def connect(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        await self.refresh_long_poll_server()

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def api(self, method: str, **params: Any) -> Any:
        if not self.session:
            raise VKApiError("VK client is not connected")

        payload = {
            "access_token": self.token,
            "v": self.API_VERSION,
            **params,
        }
        async with self.session.post(f"{self.API_URL}/{method}", data=payload) as response:
            data = await response.json(content_type=None)

        if "error" in data:
            error = data["error"]
            raise VKApiError(f"{method}: {error.get('error_msg', error)}")
        return data["response"]

    async def refresh_long_poll_server(self):
        response = await self.api("groups.getLongPollServer", group_id=self.group_id)
        self.server = response["server"]
        self.key = response["key"]
        self.ts = response["ts"]

    async def poll(self) -> list[dict[str, Any]]:
        if not self.session or not self.server or not self.key or not self.ts:
            await self.connect()

        assert self.session and self.server and self.key and self.ts
        params = {
            "act": "a_check",
            "key": self.key,
            "ts": self.ts,
            "wait": 25,
        }

        try:
            async with self.session.get(self.server, params=params, timeout=35) as response:
                data = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await asyncio.sleep(2)
            return []

        failed = data.get("failed")
        if failed == 1:
            self.ts = data["ts"]
            return []
        if failed in (2, 3):
            await self.refresh_long_poll_server()
            return []
        if failed:
            raise VKApiError(f"Long Poll failed: {failed}")

        self.ts = data["ts"]
        return data.get("updates", [])

    async def send_message(
        self,
        peer_id: int,
        text: str,
        keyboard: str | None = None,
        attachment: str | None = None,
    ):
        params: dict[str, Any] = {
            "peer_id": peer_id,
            "random_id": secrets.randbits(31),
        }
        if text:
            params["message"] = text
        if keyboard:
            params["keyboard"] = keyboard
        if attachment:
            params["attachment"] = attachment
        await self.api("messages.send", **params)
