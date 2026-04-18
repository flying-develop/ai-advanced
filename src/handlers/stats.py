"""Handler for the /stats command — shows user's conversation statistics."""

# stdlib
import logging

# third-party
from aiogram import Router, types
from aiogram.filters import Command

# local
from src.services.conversation_service import ConversationService
from src.utils.messages import STATS_NO_HISTORY, STATS_TEXT

logger = logging.getLogger(__name__)

stats_router = Router(name="stats")


@stats_router.message(Command("stats"))
async def handle_stats(
    message: types.Message,
    conversation_service: ConversationService,
) -> None:
    """Reply with the user's total conversation and message counts."""
    assert message.from_user is not None  # guaranteed by AuthMiddleware
    stats = await conversation_service.get_stats(user_id=message.from_user.id)

    if stats.message_count == 0:
        await message.answer(STATS_NO_HISTORY)
        return

    date_str = (
        stats.first_message_at.strftime("%d.%m.%Y")
        if stats.first_message_at
        else "—"
    )
    text = STATS_TEXT.format(
        conversation_count=stats.conversation_count,
        message_count=stats.message_count,
        first_message_date=date_str,
    )
    await message.answer(text)
