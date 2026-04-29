"""Settings for LLM Gateway loaded from environment / .env file."""

from pathlib import Path
from pydantic_settings import BaseSettings

# Always resolve relative to the gateway/ directory, regardless of cwd.
_GATEWAY_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "claude-haiku-4-5-20251001"
    rate_limit_rpm: int = 10
    audit_log_path: str = str(_GATEWAY_DIR / "logs" / "audit.jsonl")
    mask_secrets: bool = True

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
