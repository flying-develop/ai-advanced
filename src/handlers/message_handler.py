"""Debug logging middleware for all incoming user messages."""

# stdlib
import logging
from typing import Any, Awaitable, Callable, Dict

# third-party
from aiogram import Router
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)

message_logging_router = Router(name="message_logging")


@message_logging_router.message.outer_middleware()
async def log_incoming_message(
    handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
    event: TelegramObject,
    data: Dict[str, Any],
) -> Any:
    """Log all incoming messages at DEBUG level before delegating to handlers."""
    if isinstance(event, Message):
        user = event.from_user
        logger.debug(
            "Incoming message: user_id=%s username=%s content_type=%s text=%r",
            user.id if user else None,
            user.username if user else None,
            event.content_type,
            event.text,
        )
    return await handler(event, data)
