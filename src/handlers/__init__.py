"""Handlers package — exports all routers for registration in bot.py."""

from src.handlers.assistant import assistant_router
from src.handlers.history import history_router
from src.handlers.indirect_demo import indirect_demo_router
from src.handlers.message_handler import message_logging_router
from src.handlers.start import start_router
from src.handlers.stats import stats_router

__all__ = [
    "message_logging_router",
    "start_router",
    "stats_router",
    "history_router",
    "indirect_demo_router",
    "assistant_router",
]
