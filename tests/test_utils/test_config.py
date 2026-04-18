"""Tests for Settings validation in src/config.py."""

# third-party
import pytest
from pydantic import ValidationError


def test_max_context_messages_zero_raises() -> None:
    """Settings with max_context_messages=0 must raise a validation error."""
    from src.config import Settings

    with pytest.raises(ValidationError, match="max_context_messages must be at least 1"):
        Settings(  # type: ignore[call-arg]
            bot_token="x",
            allowed_user_id=1,
            qwen_api_key="k",
            max_context_messages=0,
        )


def test_max_context_messages_negative_raises() -> None:
    """Settings with max_context_messages<0 must raise a validation error."""
    from src.config import Settings

    with pytest.raises(ValidationError):
        Settings(  # type: ignore[call-arg]
            bot_token="x",
            allowed_user_id=1,
            qwen_api_key="k",
            max_context_messages=-5,
        )


def test_max_context_messages_one_is_valid() -> None:
    """max_context_messages=1 is the minimum valid value."""
    from src.config import Settings

    s = Settings(  # type: ignore[call-arg]
        bot_token="x",
        allowed_user_id=1,
        qwen_api_key="k",
        max_context_messages=1,
    )
    assert s.max_context_messages == 1
