"""
Settings and environment configuration for the bot.
"""
from os import getenv
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    BOT_TOKEN: str = getenv("BOT_TOKEN")
    DATABASE_URL: str = getenv("DATABASE_URL")
    ADMIN_ID: str = getenv("ADMIN_ID")

    @classmethod
    def validate(cls) -> None:
        """Validate that all required settings are present."""
        required_settings = ["BOT_TOKEN", "DATABASE_URL", "ADMIN_ID"]
        for setting in required_settings:
            if not getattr(cls, setting, None):
                raise ValueError(f"Missing required environment variable: {setting}")
