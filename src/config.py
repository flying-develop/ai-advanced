"""Application configuration — all environment variables via pydantic-settings."""

# stdlib
import logging

# third-party
from pydantic import SecretStr, field_validator
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
    exchange_api_key: SecretStr

    db_url: str = "sqlite+aiosqlite:///data/bot.db"
    exchange_api_url: str = "https://api.exchangeratesapi.io/v1/latest"
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    llm_model: str
    max_context_messages: int = 20

    # Set to False to demo unprotected mode (weak prompt, no input/output guards)
    injection_protection_enabled: bool = True

    # Set to True to enable the /indirect_demo command (requires LLM credits)
    indirect_demo_enabled: bool = False

    @field_validator("max_context_messages")
    @classmethod
    def max_context_messages_must_be_positive(cls, v: int) -> int:
        """Ensure max_context_messages is at least 1 to avoid empty LLM context."""
        if v < 1:
            raise ValueError("max_context_messages must be at least 1")
        return v


settings = Settings()  # type: ignore[call-arg]
