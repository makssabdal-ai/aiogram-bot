"""HTTP sessions with optional proxy and additional certificate chain."""

import ssl
from os import getenv

import aiohttp
import certifi


def create_http_session() -> aiohttp.ClientSession:
    context = ssl.create_default_context(cafile=certifi.where())
    if ca_file := getenv("BOT_CA_FILE"):
        context.load_verify_locations(cafile=ca_file)
    return aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=context),
        proxy=getenv("BOT_PROXY") or None,
    )
