"""Stage 2 — raw extraction: pull fields as written, no normalization."""

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

_scripts = Path(__file__).parent.parent
_multistage = Path(__file__).parent
for _p in [str(_scripts), str(_multistage)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from openai import OpenAI

from stage1_classifier import Stage1Result
from utils.openai_utils import call_with_retry_verbose, strip_json_fences

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a data extraction assistant. Extract job vacancy fields exactly as written in the text. "
    "Do not normalize or interpret — extract raw values only. "
    "Return ONLY valid JSON."
)

_USER_TEMPLATE = """\
Text language: {language}
Structure quality: {structure_quality}

Extract from this vacancy text:

{text}

Return JSON with raw extracted values:
{{
  "title_raw": "as written",
  "stack_raw": ["as written"],
  "level_raw": "as written or null",
  "salary_raw": "as written or null",
  "remote_raw": "as written or null",
  "location_raw": "as written or null",
  "experience_raw": "as written or null"
}}\
"""


@dataclass
class Stage2Result:
    """Raw extracted fields from Stage 2."""

    title_raw: str
    stack_raw: list[str] = field(default_factory=list)
    level_raw: str | None = None
    salary_raw: str | None = None
    remote_raw: str | None = None
    location_raw: str | None = None
    experience_raw: str | None = None
    tokens_used: int = 0
    latency_ms: float = 0.0


class Stage2Extractor:
    """Extracts raw vacancy fields without normalization."""

    def __init__(self, client: OpenAI) -> None:
        self._client = client

    def extract(self, text: str, stage1: Stage1Result) -> Stage2Result:
        """Return Stage2Result with raw field values from the vacancy text."""
        start = time.monotonic()
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_TEMPLATE.format(
                language=stage1.language,
                structure_quality=stage1.structure_quality,
                text=text,
            )},
        ]

        try:
            raw, tokens = call_with_retry_verbose(
                self._client, messages, model="gpt-4o-mini", temperature=0, max_tokens=300
            )
        except Exception as e:
            logger.warning("Stage2 API error: %s", e)
            elapsed = (time.monotonic() - start) * 1000
            return Stage2Result(title_raw="", tokens_used=0, latency_ms=elapsed)

        elapsed = (time.monotonic() - start) * 1000

        try:
            data = json.loads(strip_json_fences(raw))
        except json.JSONDecodeError:
            logger.warning("Stage2: response is not valid JSON: %r", raw[:80])
            return Stage2Result(title_raw="", tokens_used=tokens, latency_ms=elapsed)

        stack = data.get("stack_raw", [])
        if not isinstance(stack, list):
            stack = []

        return Stage2Result(
            title_raw=data.get("title_raw") or "",
            stack_raw=stack,
            level_raw=data.get("level_raw"),
            salary_raw=data.get("salary_raw"),
            remote_raw=data.get("remote_raw"),
            location_raw=data.get("location_raw"),
            experience_raw=data.get("experience_raw"),
            tokens_used=tokens,
            latency_ms=elapsed,
        )
