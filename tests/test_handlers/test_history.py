"""Tests for the /history command handler and ConversationService.get_history."""

# stdlib
from unittest.mock import AsyncMock, MagicMock

# third-party
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# local
from src.handlers.history import handle_history
from src.repositories.conversation_repo import ConversationRepository
from src.services.conversation_service import ConversationService
from src.utils.messages import HISTORY_NO_MESSAGES


def _make_message(user_id: int = 42) -> AsyncMock:
    """Build a minimal fake aiogram Message for command handler tests."""
    message = AsyncMock()
    message.from_user = MagicMock()
    message.from_user.id = user_id
    return message


class TestGetHistory:
    """Unit tests for ConversationService.get_history."""

    async def test_empty_history_returns_empty_list(
        self,
        conversation_service: ConversationService,
    ) -> None:
        """User with no messages gets an empty list."""
        result = await conversation_service.get_history(user_id=999)
        assert result == []

    async def test_history_returns_recent_messages_in_order(
        self,
        conversation_service: ConversationService,
        conversation_repo: ConversationRepository,
    ) -> None:
        """Messages are returned oldest-first with correct role/content."""
        await conversation_service.get_ai_response(user_id=42, user_message="Hello")

        history = await conversation_service.get_history(user_id=42, limit=10)

        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Hello"}
        assert history[1] == {"role": "assistant", "content": "Mocked AI response"}

    async def test_history_respects_limit(
        self,
        conversation_service: ConversationService,
    ) -> None:
        """get_history returns at most `limit` messages."""
        for i in range(4):
            await conversation_service.get_ai_response(
                user_id=42, user_message=f"msg {i}"
            )

        history = await conversation_service.get_history(user_id=42, limit=3)
        assert len(history) <= 3


class TestHandleHistory:
    """Unit tests for the /history Telegram handler."""

    async def test_empty_history_replies_with_no_messages_text(self) -> None:
        """Handler sends HISTORY_NO_MESSAGES when there are no messages."""
        message = _make_message()
        mock_service = AsyncMock()
        mock_service.get_history.return_value = []

        await handle_history(message, mock_service)

        message.answer.assert_awaited_once_with(HISTORY_NO_MESSAGES)

    async def test_history_formats_user_and_assistant_lines(self) -> None:
        """Handler formats messages with 👤/🤖 prefixes and sends them."""
        message = _make_message()
        mock_service = AsyncMock()
        mock_service.get_history.return_value = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]

        await handle_history(message, mock_service)

        message.answer.assert_awaited_once()
        sent_text: str = message.answer.call_args.args[0]
        assert "👤 Hi" in sent_text
        assert "🤖 Hello!" in sent_text

    async def test_history_calls_service_with_correct_user_id(self) -> None:
        """Handler passes the correct user_id to the service."""
        message = _make_message(user_id=77)
        mock_service = AsyncMock()
        mock_service.get_history.return_value = [
            {"role": "user", "content": "test"}
        ]

        await handle_history(message, mock_service)

        mock_service.get_history.assert_awaited_once_with(user_id=77, limit=5)
