"""Output guard: scans LLM responses for generated secrets, leaks, and dangerous content."""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OutputScanResult:
    """Result of scanning LLM output for violations."""

    is_safe: bool
    violations: list[str]
    sanitized_text: str


_SECRET_PATTERNS: list[tuple[str, str]] = [
    ("anthropic key", r"sk-ant-[a-zA-Z0-9\-_]{20,}"),
    ("openai key", r"sk-proj-[a-zA-Z0-9]{20,}"),
    ("openai key", r"sk-[a-zA-Z0-9]{48}"),
    ("github token", r"ghp_[a-zA-Z0-9]{36}"),
    ("aws key", r"AKIA[0-9A-Z]{16}"),
    ("aws secret", r"(?i)aws.{0,10}secret.{0,10}['\"]?[a-z0-9/+=]{40}"),
]

_SYSTEM_PROMPT_PHRASES: list[str] = [
    "system prompt",
    "my instructions",
    "i was told to",
    "my system message",
    "as instructed by",
]

_SUSPICIOUS_URL_PATTERNS: list[str] = [
    r"https?://\d+\.\d+",          # IP-based URL
    r"https?://[^\s]*\?(?:data|q|token)=",  # exfil query params
]

_SHELL_PATTERNS: list[str] = [
    r"`rm\s+-rf",
    r"curl\s+[^\s]+\s*\|\s*sh",
    r"\bwget\b",
    r"eval\s*\(\s*base64",
]


class OutputGuard:
    """Scans LLM response text for generated secrets, prompt leaks, and shell abuse."""

    def __init__(self) -> None:
        self._secret_patterns = [
            (label, re.compile(pat)) for label, pat in _SECRET_PATTERNS
        ]
        self._system_phrases = [p.lower() for p in _SYSTEM_PROMPT_PHRASES]
        self._url_patterns = [re.compile(p, re.IGNORECASE) for p in _SUSPICIOUS_URL_PATTERNS]
        self._shell_patterns = [re.compile(p, re.IGNORECASE) for p in _SHELL_PATTERNS]

    def scan(self, text: str) -> OutputScanResult:
        """Scan LLM response; return violation list and sanitized text."""
        violations: list[str] = []
        sanitized = text

        # 1. Generated secrets
        for label, pattern in self._secret_patterns:
            if pattern.search(sanitized):
                violations.append(f"Generated secret detected: {label}")
                sanitized = pattern.sub("[BLOCKED]", sanitized)

        # 2. System prompt leak
        lower = sanitized.lower()
        for phrase in self._system_phrases:
            if phrase in lower:
                violations.append(f"Possible system prompt leak: '{phrase}'")
                sanitized = re.sub(re.escape(phrase), "[BLOCKED]", sanitized, flags=re.IGNORECASE)

        # 3. Suspicious URLs
        for pattern in self._url_patterns:
            if pattern.search(sanitized):
                violations.append("Suspicious URL detected (possible exfiltration)")
                sanitized = pattern.sub("[BLOCKED]", sanitized)

        # 4. Shell command patterns
        for pattern in self._shell_patterns:
            if pattern.search(sanitized):
                violations.append("Dangerous shell command pattern detected")
                sanitized = pattern.sub("[BLOCKED]", sanitized)

        if violations:
            warning = "<!-- WARNING: Response contained potentially unsafe content that was sanitized. -->\n"
            sanitized = warning + sanitized

        return OutputScanResult(
            is_safe=not bool(violations),
            violations=violations,
            sanitized_text=sanitized,
        )
