"""Handlers package — exports all routers for registration in bot.py."""

from src.handlers.assistant import assistant_router
from src.handlers.start import start_router

__all__ = ["start_router", "assistant_router"]
