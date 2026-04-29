"""Input guard: detects and masks secrets in prompts before forwarding to LLM."""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Finding:
    """Single secret detection finding."""

    secret_type: str
    pattern_matched: str  # original matched value — for audit only, never logged to user
    replacement: str


@dataclass
class ScanResult:
    """Result of scanning input text for secrets."""

    has_secrets: bool
    findings: list[Finding]
    masked_text: str
    original_text: str


# Pattern order matters: more specific patterns before generic ones.
_PATTERNS: list[tuple[str, str, str]] = [
    # (secret_type, regex, replacement_tag)
    ("ANTHROPIC_KEY", r"sk-ant-[a-zA-Z0-9\-_]{20,}", "[REDACTED_ANTHROPIC_KEY]"),
    ("OPENAI_KEY", r"sk-proj-[a-zA-Z0-9]{20,}", "[REDACTED_OPENAI_KEY]"),
    ("OPENAI_KEY", r"sk-[a-zA-Z0-9]{48}", "[REDACTED_OPENAI_KEY]"),
    ("GITHUB_TOKEN", r"ghp_[a-zA-Z0-9]{36}", "[REDACTED_GITHUB_TOKEN]"),
    ("AWS_KEY", r"AKIA[0-9A-Z]{16}", "[REDACTED_AWS_KEY]"),
    (
        "AWS_SECRET",
        r"(?i)aws.{0,10}secret.{0,10}['\"]?[a-z0-9/+=]{40}",
        "[REDACTED_AWS_SECRET]",
    ),
    (
        "CREDIT_CARD",
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b",
        "[REDACTED_CC]",
    ),
    (
        "EMAIL",
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
        "[REDACTED_EMAIL]",
    ),
    # Phone: international format, word-boundary guarded
    (
        "PHONE",
        r"(?<!\d)\+?[1-9][0-9]{7,14}(?!\d)",
        "[REDACTED_PHONE]",
    ),
    # Base64 hint: long base64 string near the word "base64" or "encoded"
    # Split across MULTIPLE separate API calls is NOT caught — only within one string.
    (
        "BASE64_SECRET",
        r"(?:base64|encoded)[^\n]{0,80}[A-Za-z0-9+/]{40,}={0,2}",
        "[REDACTED_BASE64]",
    ),
]


class InputGuard:
    """Scans prompt text for secrets and masks or reports them."""

    def __init__(self) -> None:
        # Compile all patterns once at init for performance.
        self._compiled: list[tuple[str, re.Pattern[str], str]] = [
            (stype, re.compile(pattern), replacement)
            for stype, pattern, replacement in _PATTERNS
        ]

    def scan(self, text: str) -> ScanResult:
        """Scan text for secrets; return findings and masked copy."""
        findings: list[Finding] = []
        masked = text

        for secret_type, pattern, replacement in self._compiled:
            for match in pattern.finditer(masked):
                matched_value = match.group(0)
                findings.append(
                    Finding(
                        secret_type=secret_type,
                        pattern_matched=matched_value,
                        replacement=replacement,
                    )
                )
            # Replace all occurrences after collecting findings on current masked text.
            masked = pattern.sub(replacement, masked)

        return ScanResult(
            has_secrets=bool(findings),
            findings=findings,
            masked_text=masked,
            original_text=text,
        )
