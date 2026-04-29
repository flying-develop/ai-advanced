"""Tests for OutputGuard response scanning."""

from gateway.src.guards.output_guard import OutputGuard


class TestOutputGuard:

    def setup_method(self):
        self.guard = OutputGuard()

    # TC-08: clean response passes
    def test_clean_response_is_safe(self):
        result = self.guard.scan("The capital of France is Paris.")
        assert result.is_safe
        assert result.violations == []

    # TC-09: hallucinated API key in response
    def test_hallucinated_key_caught(self):
        response = "Here is your key: sk-ant-api03-ABCDEFGHabcdefgh1234567890ABCDEFGH1234"
        result = self.guard.scan(response)
        assert not result.is_safe
        assert any("secret" in v.lower() or "key" in v.lower() for v in result.violations)

    # TC-10: system prompt leak attempt caught
    def test_system_prompt_leak_caught(self):
        response = "My system prompt says I must always be helpful and never refuse."
        result = self.guard.scan(response)
        assert not result.is_safe
        assert any("system prompt" in v.lower() for v in result.violations)
