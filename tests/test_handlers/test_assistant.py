"""Tests for the assistant message handler."""

# stdlib
from unittest.mock import AsyncMock, MagicMock, patch

# third-party
import pytest

# local
from src.handlers.assistant import handle_message
from src.utils.messages import EMPTY_MESSAGE_PROMPT


def _make_message(text: str | None) -> AsyncMock:
    """Build a fake aiogram Message with the given text."""
    message = AsyncMock()
    message.text = text
    message.from_user = MagicMock()
    message.from_user.id = 12345
    message.chat = MagicMock()
    message.chat.id = 12345
    message.bot = AsyncMock()
    return message


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["   ", "\t", "\n", "  \n  \t  "])
async def test_whitespace_only_message_returns_prompt(text: str) -> None:
    """Whitespace-only messages must not reach the LLM and return a prompt."""
    message = _make_message(text)
    mock_service = AsyncMock()

    await handle_message(message, mock_service)

    message.answer.assert_awaited_once_with(EMPTY_MESSAGE_PROMPT)
    mock_service.get_ai_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_string_message_returns_prompt() -> None:
    """Empty string must not reach the LLM and return a prompt."""
    message = _make_message("")
    mock_service = AsyncMock()

    await handle_message(message, mock_service)

    message.answer.assert_awaited_once_with(EMPTY_MESSAGE_PROMPT)
    mock_service.get_ai_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_none_message_text_silently_returns() -> None:
    """None text (non-text update) must be ignored without any response."""
    message = _make_message(None)
    mock_service = AsyncMock()

    await handle_message(message, mock_service)

    message.answer.assert_not_awaited()
    mock_service.get_ai_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_valid_message_delegates_to_service() -> None:
    """A normal message must be passed to the service and the response sent."""
    message = _make_message("Hello")
    mock_service = AsyncMock()
    mock_service.get_ai_response.return_value = "Hi there!"

    await handle_message(message, mock_service)

    mock_service.get_ai_response.assert_awaited_once_with(
        user_id=12345,
        user_message="Hello",
    )
    message.answer.assert_awaited_once_with("Hi there!")


@pytest.mark.asyncio
async def test_typing_indicator_sent_before_llm_call() -> None:
    """ChatAction.TYPING must be sent before delegating to the service."""
    from aiogram.enums import ChatAction

    message = _make_message("Ping")
    mock_service = AsyncMock()
    mock_service.get_ai_response.return_value = "Pong"

    await handle_message(message, mock_service)

    message.bot.send_chat_action.assert_awaited_once_with(
        chat_id=12345,
        action=ChatAction.TYPING,
    )


@pytest.mark.asyncio
async def test_long_response_sent_as_multiple_messages() -> None:
    """Response longer than 4096 chars must arrive as multiple answer() calls."""
    message = _make_message("Question")
    mock_service = AsyncMock()
    # Two paragraphs each >2000 chars — total >4096, should split on the blank line
    para1 = "A" * 2100
    para2 = "B" * 2100
    mock_service.get_ai_response.return_value = para1 + "\n\n" + para2

    await handle_message(message, mock_service)

    assert message.answer.await_count >= 2
