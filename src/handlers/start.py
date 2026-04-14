"""Handlers for /start and /help commands."""

# stdlib
import logging

# third-party
from aiogram import Router, types
from aiogram.filters import Command

# local
from src.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)

start_router = Router(name="start")

_HELP_TEXT = (
    "Привет! Я твой персональный AI-ассистент.\n\n"
    "Просто напиши мне сообщение, и я отвечу.\n\n"
    "Команды:\n"
    "/start — приветствие\n"
    "/help — эта справка\n"
    "/reset — сбросить историю диалога\n"
    "/new_chat — начать новый диалог"
)


@start_router.message(Command("start"))
async def handle_start(message: types.Message) -> None:
    """Send a welcome message on /start."""
    await message.answer(_HELP_TEXT)


@start_router.message(Command("help"))
async def handle_help(message: types.Message) -> None:
    """Send a help message on /help."""
    await message.answer(_HELP_TEXT)


@start_router.message(Command("reset"))
async def handle_reset(
    message: types.Message,
    conversation_service: ConversationService,
) -> None:
    """Reset the current conversation context on /reset."""
    await conversation_service.reset_conversation(user_id=message.from_user.id)
    await message.answer("История диалога сброшена. Начинаем заново!")


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
        await message.answer(
            "Начинаю новый диалог. Контекст предыдущего разговора очищен."
        )
    else:
        await message.answer("Новый диалог начат.")
