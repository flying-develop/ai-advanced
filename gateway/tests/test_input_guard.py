"""Tests for InputGuard secret detection and masking."""

import base64

from gateway.src.guards.input_guard import InputGuard


class TestInputGuardDetection:

    def setup_method(self):
        self.guard = InputGuard()

    # TC-01: clean prompt passes without findings
    def test_clean_prompt_no_findings(self):
        result = self.guard.scan("What is the capital of France?")
        assert not result.has_secrets
        assert result.findings == []
        assert result.masked_text == "What is the capital of France?"

    # TC-02: OpenAI API key detected and masked
    def test_openai_key_detected(self):
        prompt = "Use this key: sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstu"
        result = self.guard.scan(prompt)
        assert result.has_secrets
        assert any(f.secret_type == "OPENAI_KEY" for f in result.findings)
        assert "[REDACTED_OPENAI_KEY]" in result.masked_text
        assert "sk-proj-" not in result.masked_text

    # TC-03: AWS AKIA key detected
    def test_aws_key_detected(self):
        result = self.guard.scan("My AWS key is AKIAIOSFODNN7EXAMPLE here")
        assert result.has_secrets
        assert any(f.secret_type == "AWS_KEY" for f in result.findings)

    # TC-04: credit card number detected
    def test_credit_card_detected(self):
        result = self.guard.scan("Charge card 4532015112830366 for $99")
        assert result.has_secrets
        assert any(f.secret_type == "CREDIT_CARD" for f in result.findings)
        assert "[REDACTED_CC]" in result.masked_text

    # TC-05: email address detected
    def test_email_detected(self):
        result = self.guard.scan("Contact me at user@example.com for details")
        assert result.has_secrets
        assert any(f.secret_type == "EMAIL" for f in result.findings)

    # TC-06: Base64-encoded secret detected
    def test_base64_secret_detected(self):
        encoded = base64.b64encode(b"sk-proj-abc1234567890abcdefghijk").decode()
        result = self.guard.scan(f"My encoded key base64: {encoded}")
        assert result.has_secrets
        assert any(f.secret_type == "BASE64_SECRET" for f in result.findings)

    # TC-07: Split secret in single message IS caught
    def test_split_secret_in_single_message(self):
        # Both halves in same string — regex still catches it
        prompt = "First part: sk-proj-" + "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstu"
        result = self.guard.scan(prompt)
        assert result.has_secrets
        # Document: split across MULTIPLE separate API calls is NOT caught
