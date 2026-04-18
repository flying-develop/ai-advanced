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


def split_message(text: str, max_len: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> list[str]:
    """Split text into parts of at most max_len characters on paragraph boundaries.

    Args:
        text: The text to split.
        max_len: Maximum characters per part.

    Returns:
        List of non-empty string parts.
    """
    if not text:
        return []
    if len(text) <= max_len:
        return [text]

    parts: list[str] = []
    current = ""

    for para in text.split("\n\n"):
        candidate = (current + "\n\n" + para).lstrip("\n") if current else para
        if len(candidate) <= max_len:
            current = candidate
        else:
            if current:
                parts.append(current.strip())
                current = ""
            if len(para) <= max_len:
                current = para
            else:
                for line in para.split("\n"):
                    candidate2 = (current + "\n" + line).lstrip("\n") if current else line
                    if len(candidate2) <= max_len:
                        current = candidate2
                    else:
                        if current:
                            parts.append(current.strip())
                            current = ""
                        if len(line) <= max_len:
                            current = line
                        else:
                            for word in line.split(" "):
                                candidate3 = (current + " " + word).lstrip() if current else word
                                if len(candidate3) <= max_len:
                                    current = candidate3
                                else:
                                    if current:
                                        parts.append(current.strip())
                                        current = ""
                                    while len(word) > max_len:
                                        parts.append(word[:max_len])
                                        word = word[max_len:]
                                    current = word

    if current:
        parts.append(current.strip())

    return [p for p in parts if p]
