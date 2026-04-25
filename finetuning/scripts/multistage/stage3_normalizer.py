"""Stage 3 — normalization: convert raw fields to strict schema with enums and types."""

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

from stage2_extractor import Stage2Result
from utils.openai_utils import call_with_retry_verbose, strip_json_fences

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a data normalization assistant. Convert raw job vacancy fields to a strict schema. "
    "Return ONLY valid JSON with exact types specified."
)

_USER_TEMPLATE = """\
Normalize these raw extracted fields to strict schema:

Raw data:
{stage2_json}

Return normalized JSON:
{{
  "title": "string",
  "stack": ["array of specific technologies only, no soft skills"],
  "level": "junior" | "middle" | "senior" | "lead" | "unknown",
  "salary_from": number | null,
  "currency": "RUB" | "USD" | "EUR" | null,
  "remote": "true" | "false" | "hybrid" | "unknown",
  "location": "string" | null,
  "experience_years_min": number | null,
  "experience_years_required": "normal" | "inflated" | "unknown"
}}

Rules:
- salary_from: extract minimum number only, no strings like "350 000" → 350000
- remote: "true" if fully remote, "false" if office only, "hybrid" if mixed
- stack: exclude "REST API", "Git", "Agile", "коммуникация" and similar non-tech items
- experience_years_required: "inflated" if years > 4 for roles where 2-3 years suffice with AI tools\
"""


@dataclass
class Stage3Result:
    """Normalized extraction result from Stage 3."""

    extraction: dict
    tokens_used: int
    latency_ms: float


class Stage3Normalizer:
    """Normalizes raw Stage 2 fields into the strict extraction schema."""

    def __init__(self, client: OpenAI) -> None:
        self._client = client

    def normalize(self, stage2: Stage2Result) -> Stage3Result:
        """Return Stage3Result with normalized extraction dict."""
        start = time.monotonic()

        stage2_json = json.dumps({
            "title_raw": stage2.title_raw,
            "stack_raw": stage2.stack_raw,
            "level_raw": stage2.level_raw,
            "salary_raw": stage2.salary_raw,
            "remote_raw": stage2.remote_raw,
            "location_raw": stage2.location_raw,
            "experience_raw": stage2.experience_raw,
        }, ensure_ascii=False, indent=2)

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_TEMPLATE.format(stage2_json=stage2_json)},
        ]

        try:
            raw, tokens = call_with_retry_verbose(
                self._client, messages, model="gpt-4o-mini", temperature=0, max_tokens=250
            )
        except Exception as e:
            logger.warning("Stage3 API error: %s", e)
            elapsed = (time.monotonic() - start) * 1000
            return Stage3Result(extraction={}, tokens_used=0, latency_ms=elapsed)

        elapsed = (time.monotonic() - start) * 1000

        try:
            data = json.loads(strip_json_fences(raw))
        except json.JSONDecodeError:
            logger.warning("Stage3: response is not valid JSON: %r", raw[:80])
            return Stage3Result(extraction={}, tokens_used=tokens, latency_ms=elapsed)

        return Stage3Result(extraction=data, tokens_used=tokens, latency_ms=elapsed)
