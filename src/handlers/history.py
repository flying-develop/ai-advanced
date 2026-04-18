"""Handler for the /history command — shows the last 5 messages of the current dialogue."""

# stdlib
import logging

# third-party
from aiogram import Router, types
from aiogram.filters import Command

# local
from src.services.conversation_service import ConversationService
from src.utils.messages import (
    HISTORY_ASSISTANT_PREFIX,
    HISTORY_NO_MESSAGES,
    HISTORY_USER_PREFIX,
)

logger = logging.getLogger(__name__)

history_router = Router(name="history")


@history_router.message(Command("history"))
async def handle_history(
    message: types.Message,
    conversation_service: ConversationService,
) -> None:
    """Reply with the last 5 messages of the active conversation, formatted with role icons."""
    assert message.from_user is not None  # guaranteed by AuthMiddleware

    history = await conversation_service.get_history(
        user_id=message.from_user.id, limit=5
    )

    if not history:
        await message.answer(HISTORY_NO_MESSAGES)
        return

    lines: list[str] = []
    for entry in history:
        prefix = (
            HISTORY_USER_PREFIX if entry["role"] == "user" else HISTORY_ASSISTANT_PREFIX
        )
        lines.append(f"{prefix} {entry['content']}")

    await message.answer("\n".join(lines))
