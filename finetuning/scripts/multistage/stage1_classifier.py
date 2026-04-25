"""Stage 1 — classify text: is it a job vacancy, what language, what structure quality."""

import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_scripts = Path(__file__).parent.parent
_multistage = Path(__file__).parent
for _p in [str(_scripts), str(_multistage)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from openai import OpenAI

from utils.openai_utils import call_with_retry_verbose, strip_json_fences

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a text classifier. Analyze the input text and determine if it is a job vacancy. "
    "Return ONLY valid JSON, no explanation."
)

_USER_TEMPLATE = """\
Classify this text:

{text}

Return JSON:
{{
  "is_vacancy": true | false,
  "language": "ru" | "en" | "mixed",
  "structure_quality": "high" | "medium" | "low",
  "reason": "one sentence"
}}

structure_quality:
- high: clear sections, explicit salary, level, stack
- medium: some fields implicit or missing
- low: very short, chaotic, or ambiguous text\
"""

_FAIL_RESULT_DEFAULTS = {
    "is_vacancy": False,
    "language": "unknown",
    "structure_quality": "low",
    "reason": "parse error",
}


@dataclass
class Stage1Result:
    """Classification result from Stage 1."""

    is_vacancy: bool
    language: str        # "ru" | "en" | "mixed"
    structure_quality: str  # "high" | "medium" | "low"
    reason: str
    tokens_used: int
    latency_ms: float


class Stage1Classifier:
    """Classifies text as vacancy or not, detects language and structure quality."""

    def __init__(self, client: OpenAI) -> None:
        self._client = client

    def classify(self, text: str) -> Stage1Result:
        """Return Stage1Result with vacancy flag, language, structure quality."""
        start = time.monotonic()
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_TEMPLATE.format(text=text or "(empty)")},
        ]

        try:
            raw, tokens = call_with_retry_verbose(
                self._client, messages, model="gpt-4o-mini", temperature=0, max_tokens=100
            )
        except Exception as e:
            logger.warning("Stage1 API error: %s", e)
            elapsed = (time.monotonic() - start) * 1000
            return Stage1Result(is_vacancy=False, language="unknown", structure_quality="low",
                                reason=f"api error: {e}", tokens_used=0, latency_ms=elapsed)

        elapsed = (time.monotonic() - start) * 1000

        try:
            data = json.loads(strip_json_fences(raw))
        except json.JSONDecodeError:
            logger.warning("Stage1: response is not valid JSON: %r", raw[:80])
            return Stage1Result(tokens_used=tokens, latency_ms=elapsed, **_FAIL_RESULT_DEFAULTS)

        return Stage1Result(
            is_vacancy=bool(data.get("is_vacancy", False)),
            language=data.get("language", "unknown"),
            structure_quality=data.get("structure_quality", "low"),
            reason=data.get("reason", ""),
            tokens_used=tokens,
            latency_ms=elapsed,
        )
