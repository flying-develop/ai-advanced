"""AuthMiddleware — blocks all updates from users other than ALLOWED_USER_ID."""

# stdlib
import logging
from typing import Any, Awaitable, Callable, Dict

# third-party
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

# local
from src.config import settings

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Rejects updates from any user not matching settings.allowed_user_id."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # At dp.update outer_middleware level, `event` IS the Update object directly.
        # `data["event_update"]` is only populated later inside the router chain.
        update: Update = event  # type: ignore[assignment]

        user = None
        if update.message:
            user = update.message.from_user
        elif update.callback_query:
            user = update.callback_query.from_user

        if user is None or user.id != settings.allowed_user_id:
            logger.warning(
                "Blocked unauthorized update from user_id=%s",
                user.id if user else "unknown",
            )
            return None

        return await handler(event, data)
