"""Handlers for /start and /help commands."""

# stdlib
import logging

# third-party
from aiogram import Router, types
from aiogram.filters import Command

# local
from src.services.conversation_service import ConversationService
from src.utils.messages import (
    HELP_TEXT,
    NEW_CHAT_NO_PREVIOUS,
    NEW_CHAT_STARTED,
    RESET_SUCCESS,
)

logger = logging.getLogger(__name__)

start_router = Router(name="start")


@start_router.message(Command("start"))
async def handle_start(message: types.Message) -> None:
    """Send a welcome message on /start."""
    await message.answer(HELP_TEXT)


@start_router.message(Command("help"))
async def handle_help(message: types.Message) -> None:
    """Send a help message on /help."""
    await message.answer(HELP_TEXT)


@start_router.message(Command("reset"))
async def handle_reset(
    message: types.Message,
    conversation_service: ConversationService,
) -> None:
    """Reset the current conversation context on /reset."""
    await conversation_service.reset_conversation(user_id=message.from_user.id)
    await message.answer(RESET_SUCCESS)


@start_router.message(Command("new_chat"))
async def handle_new_chat(
    message: types.Message,
    conversation_service: ConversationService,
) -> None:
    """Start a fresh conversation on /new_chat, closing the previous one."""
    had_previous = await conversation_service.start_new_conversation(
        user_id=message.from_user.id,
    )
    if had_previous:
        await message.answer(NEW_CHAT_STARTED)
    else:
        await message.answer(NEW_CHAT_NO_PREVIOUS)
