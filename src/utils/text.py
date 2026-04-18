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


def split_message(text: str, max_len: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> list[str]:
    """Split text into parts of at most max_len characters, breaking on paragraph boundaries.

    Tries to split on double-newlines first; if a paragraph itself exceeds max_len
    it is further split on single newlines, then on spaces, and finally hard-cut.

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

    def flush(chunk: str) -> None:
        nonlocal current
        if current:
            parts.append(current.strip())
            current = ""
        if chunk:
            parts.append(chunk.strip())

    paragraphs = text.split("\n\n")
    for para in paragraphs:
        candidate = (current + "\n\n" + para).lstrip("\n") if current else para
        if len(candidate) <= max_len:
            current = candidate
        else:
            # flush current accumulator
            if current:
                parts.append(current.strip())
                current = ""
            # paragraph itself may be too long — split by single newlines
            if len(para) <= max_len:
                current = para
            else:
                lines = para.split("\n")
                for line in lines:
                    candidate2 = (current + "\n" + line).lstrip("\n") if current else line
                    if len(candidate2) <= max_len:
                        current = candidate2
                    else:
                        if current:
                            parts.append(current.strip())
                            current = ""
                        # line itself may be too long — split by words
                        if len(line) <= max_len:
                            current = line
                        else:
                            words = line.split(" ")
                            for word in words:
                                candidate3 = (current + " " + word).lstrip() if current else word
                                if len(candidate3) <= max_len:
                                    current = candidate3
                                else:
                                    if current:
                                        parts.append(current.strip())
                                        current = ""
                                    # word longer than max_len — hard cut
                                    while len(word) > max_len:
                                        parts.append(word[:max_len])
                                        word = word[max_len:]
                                    current = word

    if current:
        parts.append(current.strip())

    return [p for p in parts if p]
