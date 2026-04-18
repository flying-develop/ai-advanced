"""Tests for src/utils/text.py — split_message."""

# local
from src.utils.text import split_message


def test_short_text_returns_single_part() -> None:
    """Text within max_len is returned as a single-element list."""
    result = split_message("Hello world", max_len=4096)
    assert result == ["Hello world"]


def test_empty_string_returns_empty_list() -> None:
    """Empty input produces no parts."""
    result = split_message("", max_len=4096)
    assert result == []


def test_text_exactly_at_limit_is_not_split() -> None:
    """Text of exactly max_len characters is returned unsplit."""
    text = "a" * 100
    result = split_message(text, max_len=100)
    assert result == [text]


def test_text_split_on_paragraph_boundary() -> None:
    """Text longer than max_len is split on double-newline boundaries."""
    para1 = "a" * 50
    para2 = "b" * 50
    text = para1 + "\n\n" + para2
    result = split_message(text, max_len=60)
    assert len(result) == 2
    assert para1 in result[0]
    assert para2 in result[1]


def test_no_word_is_cut_mid_word_for_normal_text() -> None:
    """Words are not cut in the middle when splitting on spaces."""
    words = ["word" + str(i) for i in range(20)]
    text = " ".join(words)
    result = split_message(text, max_len=30)
    for part in result:
        assert " " not in part or all(w in words for w in part.split())


def test_all_content_preserved_after_split() -> None:
    """Concatenation of all parts contains all original non-whitespace content."""
    text = "Para one.\n\nPara two.\n\nPara three with more content here."
    result = split_message(text, max_len=20)
    joined = " ".join(result)
    for word in text.split():
        assert word in joined


def test_each_part_within_max_len() -> None:
    """Every returned part must be at most max_len characters."""
    text = "x " * 300
    result = split_message(text, max_len=50)
    for part in result:
        assert len(part) <= 50


def test_long_single_word_hard_cut() -> None:
    """A single word longer than max_len is hard-cut at the limit."""
    word = "a" * 250
    result = split_message(word, max_len=100)
    assert all(len(p) <= 100 for p in result)
    assert "".join(result) == word
