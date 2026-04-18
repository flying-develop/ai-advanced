"""Utils package — formatting and text helpers."""

from src.utils.text import split_message, truncate
from src.utils.messages import (
    EMPTY_MESSAGE_PROMPT,
    HELP_TEXT,
    HISTORY_ASSISTANT_PREFIX,
    HISTORY_NO_MESSAGES,
    HISTORY_USER_PREFIX,
    INTERNAL_ERROR_MESSAGE,
    LLM_ERROR_FALLBACK,
    NEW_CHAT_NO_PREVIOUS,
    NEW_CHAT_STARTED,
    RESET_SUCCESS,
    STATS_NO_HISTORY,
    STATS_TEXT,
)

__all__ = [
    "split_message",
    "truncate",
    "EMPTY_MESSAGE_PROMPT",
    "HELP_TEXT",
    "HISTORY_ASSISTANT_PREFIX",
    "HISTORY_NO_MESSAGES",
    "HISTORY_USER_PREFIX",
    "INTERNAL_ERROR_MESSAGE",
    "LLM_ERROR_FALLBACK",
    "NEW_CHAT_NO_PREVIOUS",
    "NEW_CHAT_STARTED",
    "RESET_SUCCESS",
    "STATS_NO_HISTORY",
    "STATS_TEXT",
]
