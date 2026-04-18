"""Utils package — formatting and text helpers."""

from src.utils.text import split_message, truncate
from src.utils.messages import (
    HELP_TEXT,
    RESET_SUCCESS,
    NEW_CHAT_STARTED,
    NEW_CHAT_NO_PREVIOUS,
    EMPTY_MESSAGE_PROMPT,
    LLM_ERROR_FALLBACK,
    STATS_TEXT,
    STATS_NO_HISTORY,
    HISTORY_NO_MESSAGES,
    HISTORY_USER_PREFIX,
    HISTORY_ASSISTANT_PREFIX,
)

__all__ = [
    "split_message",
    "truncate",
    "HELP_TEXT",
    "RESET_SUCCESS",
    "NEW_CHAT_STARTED",
    "NEW_CHAT_NO_PREVIOUS",
    "EMPTY_MESSAGE_PROMPT",
    "LLM_ERROR_FALLBACK",
    "STATS_TEXT",
    "STATS_NO_HISTORY",
    "HISTORY_NO_MESSAGES",
    "HISTORY_USER_PREFIX",
    "HISTORY_ASSISTANT_PREFIX",
]
