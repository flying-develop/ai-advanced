"""Unit tests for AuthMiddleware."""

# stdlib
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

# local
from src.middlewares.auth import AuthMiddleware

ALLOWED_ID = 12345
BLOCKED_ID = 99999


def _make_update(user_id: int | None) -> MagicMock:
    """Build a minimal mock Update with a message.from_user carrying user_id."""
    update = MagicMock()
    update.callback_query = None
    if user_id is None:
        update.message = None
    else:
        user = MagicMock()
        user.id = user_id
        message = MagicMock()
        message.from_user = user
        update.message = message
    return update


async def test_authorized_user_passes_through_to_handler() -> None:
    """Authorized user (matching allowed_user_id) → handler is called and result returned."""
    handler = AsyncMock(return_value="ok")
    middleware = AuthMiddleware()
    data: Dict[str, Any] = {"event_update": _make_update(ALLOWED_ID)}

    with patch("src.middlewares.auth.settings") as mock_settings:
        mock_settings.allowed_user_id = ALLOWED_ID
        result = await middleware(handler, MagicMock(), data)

    handler.assert_called_once()
    assert result == "ok"


async def test_unauthorized_user_is_blocked() -> None:
    """Unauthorized user → handler is NOT called, None is returned."""
    handler = AsyncMock(return_value="should not reach")
    middleware = AuthMiddleware()
    data: Dict[str, Any] = {"event_update": _make_update(BLOCKED_ID)}

    with patch("src.middlewares.auth.settings") as mock_settings:
        mock_settings.allowed_user_id = ALLOWED_ID
        result = await middleware(handler, MagicMock(), data)

    handler.assert_not_called()
    assert result is None


async def test_update_without_from_user_is_blocked() -> None:
    """Update with no identifiable user (no message, no callback_query) → blocked."""
    handler = AsyncMock(return_value="should not reach")
    middleware = AuthMiddleware()
    # No message and no callback_query → user cannot be determined
    data: Dict[str, Any] = {"event_update": _make_update(user_id=None)}

    with patch("src.middlewares.auth.settings") as mock_settings:
        mock_settings.allowed_user_id = ALLOWED_ID
        result = await middleware(handler, MagicMock(), data)

    handler.assert_not_called()
    assert result is None


async def test_missing_event_update_key_is_blocked() -> None:
    """data dict without 'event_update' key → blocked without raising."""
    handler = AsyncMock()
    middleware = AuthMiddleware()

    with patch("src.middlewares.auth.settings") as mock_settings:
        mock_settings.allowed_user_id = ALLOWED_ID
        result = await middleware(handler, MagicMock(), {})

    handler.assert_not_called()
    assert result is None
