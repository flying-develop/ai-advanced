"""Unit tests for ConversationService."""

# stdlib
from unittest.mock import AsyncMock

# third-party
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# local
from src.models.conversation import Conversation, Message
from src.repositories.conversation_repo import ConversationRepository
from src.services.conversation_service import ConversationService
from src.services.llm_service import LLMServiceError


class TestGetAiResponse:
    """Tests for ConversationService.get_ai_response."""

    async def test_happy_path_saves_messages_and_returns_response(
        self,
        conversation_service: ConversationService,
        mock_llm_service: AsyncMock,
        session: AsyncSession,
    ) -> None:
        """Happy path: user message saved, LLM called once, response saved and returned."""
        response = await conversation_service.get_ai_response(
            user_id=42, user_message="Hello!"
        )

        assert response == "Mocked AI response"
        mock_llm_service.complete.assert_called_once()

        result = await session.execute(select(Message).order_by(Message.id))
        messages = list(result.scalars().all())
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Hello!"
        assert messages[1].role == "assistant"
        assert messages[1].content == "Mocked AI response"

    async def test_llm_error_returns_fallback_message(
        self,
        conversation_service: ConversationService,
        mock_llm_service: AsyncMock,
    ) -> None:
        """LLM failure: service catches LLMServiceError and returns a human-readable fallback."""
        mock_llm_service.complete.side_effect = LLMServiceError("API is down")

        response = await conversation_service.get_ai_response(
            user_id=42, user_message="Hello?"
        )

        assert "ошибка" in response.lower()
        assert response != "Hello?"

    async def test_empty_message_still_delegates_to_llm(
        self,
        conversation_service: ConversationService,
        mock_llm_service: AsyncMock,
    ) -> None:
        """Edge case: empty string is not filtered by service — LLM is still called.

        The guard lives in the handler layer; service is content-agnostic.
        """
        response = await conversation_service.get_ai_response(
            user_id=42, user_message=""
        )

        assert response == "Mocked AI response"
        mock_llm_service.complete.assert_called_once()

    async def test_context_respects_max_context_messages_limit(
        self,
        conversation_service: ConversationService,
        mock_llm_service: AsyncMock,
        conversation_repo: ConversationRepository,
    ) -> None:
        """Context window: LLM receives at most max_context_messages messages."""
        from src.config import settings

        conv = await conversation_repo.get_or_create(user_id=42)
        # Pre-populate more messages than the limit
        for i in range(settings.max_context_messages + 5):
            await conversation_repo.add_message(
                conversation_id=conv.id, role="user", content=f"old msg {i}"
            )

        await conversation_service.get_ai_response(user_id=42, user_message="new msg")

        messages_sent = mock_llm_service.complete.call_args.kwargs["messages"]
        # +1 because service adds the new user message before fetching context
        assert len(messages_sent) <= settings.max_context_messages

    async def test_second_call_reuses_same_conversation(
        self,
        conversation_service: ConversationService,
        session: AsyncSession,
    ) -> None:
        """Same user_id always reuses the single active conversation."""
        await conversation_service.get_ai_response(user_id=42, user_message="First")
        await conversation_service.get_ai_response(user_id=42, user_message="Second")

        result = await session.execute(
            select(Conversation).where(Conversation.user_id == 42)
        )
        conversations = list(result.scalars().all())
        assert len(conversations) == 1


class TestStartNewConversation:
    """Tests for ConversationService.start_new_conversation."""

    async def test_deactivates_old_conversation_and_flags_had_previous(
        self,
        conversation_service: ConversationService,
        conversation_repo: ConversationRepository,
    ) -> None:
        """start_new_conversation deactivates old conv and returns True."""
        old_conv = await conversation_repo.get_or_create(user_id=99)
        old_id = old_conv.id

        had_previous = await conversation_service.start_new_conversation(user_id=99)

        assert had_previous is True
        refreshed = await conversation_repo.get_by_id(old_id)
        assert refreshed is not None
        assert refreshed.is_active is False

    async def test_new_message_goes_to_new_conversation_after_reset(
        self,
        conversation_service: ConversationService,
        conversation_repo: ConversationRepository,
    ) -> None:
        """After start_new_conversation the next message lands in a fresh conversation."""
        old_conv = await conversation_repo.get_or_create(user_id=99)
        old_id = old_conv.id

        await conversation_service.start_new_conversation(user_id=99)
        await conversation_service.get_ai_response(user_id=99, user_message="New start")

        new_conv = await conversation_repo.get_active(user_id=99)
        assert new_conv is not None
        assert new_conv.id != old_id

    async def test_returns_false_when_no_active_conversation_exists(
        self,
        conversation_service: ConversationService,
    ) -> None:
        """start_new_conversation returns False when there is nothing to deactivate."""
        had_previous = await conversation_service.start_new_conversation(user_id=999)
        assert had_previous is False
