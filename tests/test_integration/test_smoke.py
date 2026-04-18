"""Integration smoke tests — full user-flow scenarios through the service layer."""

# stdlib
from unittest.mock import AsyncMock

# third-party
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# local
from src.models.conversation import Conversation, Message
from src.repositories.conversation_repo import ConversationRepository
from src.services.conversation_service import ConversationService


async def test_smoke_start_command_sends_welcome_text() -> None:
    """Scenario 1 — /start: handler calls message.answer with the welcome text."""
    from src.handlers.start import handle_start
    from src.utils.messages import HELP_TEXT

    mock_message = AsyncMock()
    await handle_start(mock_message)

    mock_message.answer.assert_called_once_with(HELP_TEXT)
    assert "ассистент" in HELP_TEXT.lower() or "/start" in HELP_TEXT


async def test_smoke_ai_dialogue_messages_persisted_in_db(
    conversation_service: ConversationService,
    mock_llm_service: AsyncMock,
    session: AsyncSession,
) -> None:
    """Scenario 2 — Dialogue with AI: response returned, both messages stored in DB."""
    mock_llm_service.complete.return_value = "AI says hello!"

    response = await conversation_service.get_ai_response(
        user_id=1, user_message="Hi there"
    )

    assert response == "AI says hello!"
    mock_llm_service.complete.assert_called_once()

    result = await session.execute(select(Message).order_by(Message.id))
    messages = list(result.scalars().all())
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "Hi there"
    assert messages[1].role == "assistant"
    assert messages[1].content == "AI says hello!"

    conv_result = await session.execute(
        select(Conversation).where(Conversation.user_id == 1)
    )
    assert conv_result.scalar_one_or_none() is not None


async def test_smoke_new_chat_no_prior_conversation_creates_fresh_one(
    conversation_service: ConversationService,
    conversation_repo: ConversationRepository,
) -> None:
    """Scenario 3b — /new_chat with no prior conversation: returns False, new conv created."""
    had_previous = await conversation_service.start_new_conversation(user_id=555)

    assert had_previous is False
    new_conv = await conversation_repo.get_active(user_id=555)
    assert new_conv is not None


async def test_smoke_new_chat_deactivates_old_conversation_and_routes_to_new(
    conversation_service: ConversationService,
    conversation_repo: ConversationRepository,
    mock_llm_service: AsyncMock,
) -> None:
    """Scenario 3 — /new_chat: old conversation deactivated, next message in fresh conversation."""
    # First dialogue creates an active conversation
    await conversation_service.get_ai_response(user_id=1, user_message="First message")
    old_conv = await conversation_repo.get_active(user_id=1)
    assert old_conv is not None
    old_id = old_conv.id

    # User triggers /new_chat
    had_previous = await conversation_service.start_new_conversation(user_id=1)
    assert had_previous is True

    # Old conversation must now be inactive
    refreshed_old = await conversation_repo.get_by_id(old_id)
    assert refreshed_old is not None
    assert refreshed_old.is_active is False

    # Next message goes into a brand-new conversation
    await conversation_service.get_ai_response(user_id=1, user_message="Fresh start")

    new_conv = await conversation_repo.get_active(user_id=1)
    assert new_conv is not None
    assert new_conv.id != old_id
