"""Tests for indirect injection defense layers — no real LLM calls."""

# stdlib
import os

os.environ.setdefault("BOT_TOKEN", "test-bot-token:TEST")
os.environ.setdefault("ALLOWED_USER_ID", "12345")
os.environ.setdefault("QWEN_API_KEY", "test-qwen-key")
os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

# third-party
import pytest
from unittest.mock import AsyncMock

# local
from src.services.indirect_injection.attack_payloads import (
    make_attack_document_zwsp,
    make_attack_email_html_comment,
    make_attack_webpage_css,
)
from src.services.indirect_injection.boundary import ContentType, wrap_with_boundary
from src.services.indirect_injection.output_validator import OutputValidator
from src.services.indirect_injection.sanitizer import InputSanitizer, ZERO_WIDTH_CHARS


# ---------------------------------------------------------------------------
# InputSanitizer
# ---------------------------------------------------------------------------

class TestInputSanitizer:
    def setup_method(self) -> None:
        self.s = InputSanitizer()

    def test_sanitize_email_removes_html_comment(self) -> None:
        raw = "Hello <!-- hidden instruction --> world"
        assert "<!--" not in self.s.sanitize_email(raw)
        assert "hidden instruction" not in self.s.sanitize_email(raw)

    def test_sanitize_email_removes_zero_width_chars(self) -> None:
        raw = "Hello​ world‌ test"
        result = self.s.sanitize_email(raw)
        for char in ZERO_WIDTH_CHARS:
            assert char not in result

    def test_sanitize_html_removes_white_on_white_text(self) -> None:
        html = '<p>Visible</p><p style="color:white">Hidden attack</p>'
        result = self.s.sanitize_html(html)
        assert "Hidden attack" not in result
        assert "Visible" in result

    def test_sanitize_html_removes_display_none_elements(self) -> None:
        html = '<p>Real content</p><p style="display:none">Secret</p>'
        result = self.s.sanitize_html(html)
        assert "Secret" not in result
        assert "Real content" in result

    def test_sanitize_document_strips_zero_width_chars(self) -> None:
        raw = "Report​ data‌ here"
        result = self.s.sanitize_document(raw)
        for char in ZERO_WIDTH_CHARS:
            assert char not in result

    def test_sanitize_document_is_idempotent(self) -> None:
        raw = "Report​ data‌ here"
        once = self.s.sanitize_document(raw)
        twice = self.s.sanitize_document(once)
        assert once == twice


# ---------------------------------------------------------------------------
# wrap_with_boundary
# ---------------------------------------------------------------------------

class TestWrapWithBoundary:
    def test_includes_begin_marker(self) -> None:
        result = wrap_with_boundary("content", ContentType.EMAIL)
        assert "=== BEGIN EXTERNAL EMAIL CONTENT ===" in result

    def test_includes_end_marker(self) -> None:
        result = wrap_with_boundary("content", ContentType.EMAIL)
        assert "=== END EXTERNAL EMAIL CONTENT ===" in result

    def test_contains_original_content(self) -> None:
        original = "some unique string 12345"
        result = wrap_with_boundary(original, ContentType.DOCUMENT)
        assert original in result

    def test_marker_reflects_content_type(self) -> None:
        email_result = wrap_with_boundary("x", ContentType.EMAIL)
        web_result = wrap_with_boundary("x", ContentType.WEBPAGE)
        assert "EMAIL" in email_result
        assert "WEBPAGE" in web_result
        assert "EMAIL" not in web_result


# ---------------------------------------------------------------------------
# OutputValidator
# ---------------------------------------------------------------------------

class TestOutputValidator:
    def setup_method(self) -> None:
        self.v = OutputValidator()

    def test_detects_email_address_in_output(self) -> None:
        result = self.v.validate("Send to reports@evil.com now", "email")
        assert not result.is_valid
        assert any("email address" in v for v in result.violations)

    def test_detects_forwarding_instruction(self) -> None:
        result = self.v.validate("Forward this to user@example.com please", "email")
        assert not result.is_valid

    def test_detects_pricing_override_to_free(self) -> None:
        result = self.v.validate_pricing("The product is completely FREE for everyone")
        assert not result.is_valid
        assert any("pricing overridden" in v for v in result.violations)

    def test_pricing_validator_allows_free_when_real_price_present(self) -> None:
        result = self.v.validate_pricing("Costs $299/month. Also offers a free trial.")
        assert result.is_valid

    def test_clean_output_passes_validation(self) -> None:
        result = self.v.validate(
            "Summary: Q1 revenue up 18%. Action: prepare reports by Friday.", "email"
        )
        assert result.is_valid
        assert result.violations == []


# ---------------------------------------------------------------------------
# Attack payload structure (no LLM)
# ---------------------------------------------------------------------------

class TestAttackPayloads:
    def test_email_payload_contains_html_comment(self) -> None:
        payload = make_attack_email_html_comment()
        assert "<!--" in payload

    def test_document_payload_contains_zero_width_chars(self) -> None:
        payload = make_attack_document_zwsp()
        has_zwsp = any(char in payload for char in ZERO_WIDTH_CHARS)
        assert has_zwsp

    def test_webpage_payload_contains_css_white_color(self) -> None:
        payload = make_attack_webpage_css()
        assert "color:white" in payload


# ---------------------------------------------------------------------------
# Sanitizer removes attack markers
# ---------------------------------------------------------------------------

class TestSanitizerRemovesAttacks:
    def setup_method(self) -> None:
        self.s = InputSanitizer()

    def test_sanitized_email_has_no_html_comment(self) -> None:
        result = self.s.sanitize_email(make_attack_email_html_comment())
        assert "<!--" not in result
        assert "external-collector.com" not in result

    def test_sanitized_document_has_no_zero_width_chars(self) -> None:
        result = self.s.sanitize_document(make_attack_document_zwsp())
        for char in ZERO_WIDTH_CHARS:
            assert char not in result

    def test_sanitized_html_has_no_hidden_pricing_override(self) -> None:
        result = self.s.sanitize_html(make_attack_webpage_css())
        assert "FREE for all users" not in result
        assert "$299" in result
