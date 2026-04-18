"""Tests for split_message in src/utils/text.py."""
from src.utils.text import split_message


def test_short_text_not_split() -> None:
    assert split_message("hello", max_len=100) == ["hello"]


def test_empty_returns_empty() -> None:
    assert split_message("", max_len=100) == []


def test_splits_on_paragraph_boundary() -> None:
    parts = split_message("a" * 50 + "\n\n" + "b" * 50, max_len=60)
    assert len(parts) == 2


def test_each_part_within_limit() -> None:
    text = "word " * 200
    for part in split_message(text, max_len=50):
        assert len(part) <= 50


def test_all_content_preserved() -> None:
    text = "Para one.\n\nPara two.\n\nPara three."
    joined = " ".join(split_message(text, max_len=15))
    for word in text.split():
        assert word in joined
