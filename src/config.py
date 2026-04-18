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
        extra="ignore",
    )

    bot_token: str
    allowed_user_id: int
    qwen_api_key: str

    db_url: str = "sqlite+aiosqlite:///data/bot.db"
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-plus"
    max_context_messages: int = 20


settings = Settings()  # type: ignore[call-arg]
