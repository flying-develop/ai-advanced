"""Self-check: second independent extraction to resolve UNSURE confidence scores."""

import json
import logging
import time
from dataclasses import dataclass, field

from openai import OpenAI, RateLimitError, APIError

logger = logging.getLogger(__name__)

CRITICAL_FIELDS = {"level", "remote", "salary_from", "stack"}

SYSTEM_PROMPT = (
    "You are a structured data extraction assistant. Extract job vacancy information "
    "into a strict JSON format. Always return valid JSON only, no explanation."
)

EXTRACTION_PROMPT = """Extract the following fields from the job vacancy text:

{
  "title": "job title (string)",
  "stack": ["array of specific technologies/tools/languages/frameworks — no soft skills"],
  "level": "junior | middle | senior | lead | unknown",
  "salary_from": <minimum salary as a number or null — take exactly as written, do not convert>,
  "currency": "RUB | USD | EUR | null",
  "remote": "true | false | hybrid | unknown",
  "location": "city/location string or null",
  "experience_years_min": <minimum years required as a number or null>,
  "experience_years_required": "normal | inflated | unknown"
}

Rules:
- experience_years_required: 'inflated' if requirements are clearly above market. 'normal' if adequate. 'unknown' if unclear.
- salary_from: minimum of the range exactly as stated. null if not specified.
- stack: only concrete technologies, languages, frameworks, tools — never soft skills.
- level: infer from job title, required experience, and responsibilities combined.

Return only valid JSON, no markdown, no explanation.

Vacancy text:
"""


@dataclass
class SelfCheckResult:
    """Result of self-check comparison between two extractions."""

    agreed_fields: list[str] = field(default_factory=list)
    disagreed_fields: list[str] = field(default_factory=list)
    final_status: str = "FAIL"  # "OK" | "FAIL"
    merged_extraction: dict = field(default_factory=dict)


class SelfChecker:
    """Runs a second independent extraction and compares with the first to resolve UNSURE."""

    def __init__(self, client: OpenAI) -> None:
        self._client = client

    def check(self, vacancy_text: str, first_extraction: dict) -> SelfCheckResult:
        """
        Perform second extraction, compare critical fields, return SelfCheckResult.
        OK if >= 75% of critical fields agree; FAIL otherwise.
        """
        raw = self._call_with_retry(vacancy_text)

        try:
            second_extraction = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("SelfChecker: second extraction is not valid JSON")
            return SelfCheckResult(
                final_status="FAIL",
                merged_extraction=first_extraction,
            )

        agreed: list[str] = []
        disagreed: list[str] = []

        for field_name in CRITICAL_FIELDS:
            v1 = first_extraction.get(field_name)
            v2 = second_extraction.get(field_name)

            if _fields_agree(field_name, v1, v2):
                agreed.append(field_name)
            else:
                disagreed.append(field_name)
                logger.debug("SelfChecker: disagreement on '%s': %r vs %r", field_name, v1, v2)

        agreement_ratio = len(agreed) / len(CRITICAL_FIELDS)
        final_status = "OK" if agreement_ratio >= 0.75 else "FAIL"

        logger.debug(
            "SelfChecker: agreed=%d/%d (%.0f%%) → %s",
            len(agreed),
            len(CRITICAL_FIELDS),
            agreement_ratio * 100,
            final_status,
        )

        return SelfCheckResult(
            agreed_fields=agreed,
            disagreed_fields=disagreed,
            final_status=final_status,
            merged_extraction=first_extraction,
        )

    def _call_with_retry(self, vacancy_text: str, max_retries: int = 3) -> str:
        """Call gpt-4o-mini with temperature=0.3 and exponential backoff retry."""
        for attempt in range(max_retries):
            try:
                response = self._client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": EXTRACTION_PROMPT + vacancy_text},
                    ],
                    temperature=0.3,
                    max_tokens=512,
                )
                return response.choices[0].message.content or ""
            except RateLimitError:
                wait = 2 ** attempt * 5
                logger.warning("Rate limit hit, waiting %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                time.sleep(wait)
            except APIError as e:
                wait = 2 ** attempt * 2
                logger.warning("API error: %s, waiting %ds (attempt %d/%d)", e, wait, attempt + 1, max_retries)
                if attempt == max_retries - 1:
                    raise
                time.sleep(wait)
        raise RuntimeError("Max retries exceeded")


def _fields_agree(field_name: str, v1: object, v2: object) -> bool:
    """Check whether two field values agree (special handling for stack list)."""
    if field_name == "stack":
        if not isinstance(v1, list) or not isinstance(v2, list):
            return v1 == v2
        set1 = {s.lower().strip() for s in v1 if isinstance(s, str)}
        set2 = {s.lower().strip() for s in v2 if isinstance(s, str)}
        if not set1 and not set2:
            return True
        if not set1 or not set2:
            return False
        overlap = len(set1 & set2) / max(len(set1), len(set2))
        return overlap >= 0.5
    return v1 == v2
