"""Handlers package — exports all routers for registration in bot.py."""

from src.handlers.assistant import assistant_router
from src.handlers.start import start_router
from src.handlers.stats import stats_router

__all__ = ["start_router", "stats_router", "assistant_router"]
