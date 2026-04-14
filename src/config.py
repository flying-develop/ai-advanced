"""Application configuration — all environment variables via pydantic-settings."""

# stdlib
import logging

# third-party
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    bot_token: str
    allowed_user_id: int
    anthropic_api_key: str

    db_url: str = "sqlite+aiosqlite:///data/bot.db"
    llm_model: str = "claude-sonnet-4-20250514"
    max_context_messages: int = 20


settings = Settings()
