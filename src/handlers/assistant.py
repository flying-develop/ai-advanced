"""Handler for plain text messages — delegates to ConversationService."""

# stdlib
import logging

# third-party
from aiogram import F, Router, types
from aiogram.enums import ChatAction

# local
from src.services.conversation_service import ConversationService
from src.utils.messages import EMPTY_MESSAGE_PROMPT

logger = logging.getLogger(__name__)

assistant_router = Router(name="assistant")


@assistant_router.message(F.text)
async def handle_message(
    message: types.Message,
    conversation_service: ConversationService,
) -> None:
    """Handle incoming text message — delegate to ConversationService."""
    user_text = message.text
    if user_text is None:
        return
    if not user_text.strip():
        await message.answer(EMPTY_MESSAGE_PROMPT)
        return

    logger.info("Received message from user_id=%s", message.from_user.id)

    await message.bot.send_chat_action(
        chat_id=message.chat.id,
        action=ChatAction.TYPING,
    )

    response = await conversation_service.get_ai_response(
        user_id=message.from_user.id,
        user_message=user_text,
    )
    await message.answer(response)
