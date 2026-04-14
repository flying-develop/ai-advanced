"""Handler for plain text messages — delegates to ConversationService."""

# stdlib
import logging

# third-party
from aiogram import F, Router, types

# local
from src.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)

assistant_router = Router(name="assistant")


@assistant_router.message(F.text)
async def handle_message(
    message: types.Message,
    conversation_service: ConversationService,
) -> None:
    """Handle incoming text message — delegate to ConversationService."""
    user_text = message.text
    if not user_text:
        return

    logger.info("Received message from user_id=%s", message.from_user.id)

    response = await conversation_service.get_ai_response(
        user_id=message.from_user.id,
        user_message=user_text,
    )
    await message.answer(response)
