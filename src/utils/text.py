"""Text utility functions — formatting and truncation helpers."""

# stdlib
import logging

logger = logging.getLogger(__name__)

MAX_TELEGRAM_MESSAGE_LENGTH = 4096


def truncate(text: str, max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> str:
    """Truncate text to max_length, appending '…' if cut.

    Args:
        text: The string to truncate.
        max_length: Maximum allowed length.

    Returns:
        Original text if within limit, otherwise truncated with ellipsis.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def split_long_message(text: str, chunk_size: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> list[str]:
    """Split a long string into chunks of at most chunk_size characters.

    Args:
        text: The text to split.
        chunk_size: Maximum size per chunk.

    Returns:
        List of string chunks.
    """
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
