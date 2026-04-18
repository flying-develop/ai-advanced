"""Tests for Settings validation."""
import pytest
from pydantic import ValidationError


def test_max_context_messages_zero_raises() -> None:
    from src.config import Settings
    with pytest.raises(ValidationError, match="at least 1"):
        Settings(bot_token="x", allowed_user_id=1, qwen_api_key="k", max_context_messages=0)  # type: ignore[call-arg]


def test_max_context_messages_one_valid() -> None:
    from src.config import Settings
    s = Settings(bot_token="x", allowed_user_id=1, qwen_api_key="k", max_context_messages=1)  # type: ignore[call-arg]
    assert s.max_context_messages == 1
