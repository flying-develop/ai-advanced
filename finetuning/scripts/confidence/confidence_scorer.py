"""Confidence scoring — model evaluates its own extraction quality."""

import json
import logging
import time
from dataclasses import dataclass, field

from openai import OpenAI, RateLimitError, APIError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a quality control assistant for job vacancy data extraction.\n"
    "You will receive: original vacancy text and extracted JSON.\n"
    "Your task: evaluate confidence in the extraction quality.\n\n"
    "Return ONLY valid JSON:\n"
    "{\n"
    '  "status": "OK" | "UNSURE" | "FAIL",\n'
    '  "score": 0.0-1.0,\n'
    '  "uncertain_fields": ["field1", "field2"],\n'
    '  "reason": "brief explanation in English"\n'
    "}\n\n"
    "Scoring rules:\n"
    "- OK (score >= 0.85): all critical fields extracted clearly, format correct\n"
    "- UNSURE (score 0.5-0.84): 1-2 fields ambiguous, salary unclear, level inferred\n"
    "- FAIL (score < 0.5): critical fields missing, text is not a job vacancy, extraction unreliable"
)


@dataclass
class ScoringResult:
    """Result of model confidence scoring."""

    status: str  # "OK" | "UNSURE" | "FAIL"
    score: float
    uncertain_fields: list[str] = field(default_factory=list)
    reason: str = ""


class ConfidenceScorer:
    """Asks the model to evaluate its own extraction confidence."""

    def __init__(self, client: OpenAI) -> None:
        self._client = client

    def score(self, vacancy_text: str, extraction: dict) -> ScoringResult:
        """Return ScoringResult with status, score, uncertain_fields, and reason."""
        user_content = (
            f"Vacancy text:\n{vacancy_text}\n\n"
            f"Extracted JSON:\n{json.dumps(extraction, ensure_ascii=False, indent=2)}"
        )

        raw = self._call_with_retry(user_content)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("ConfidenceScorer: response is not valid JSON, treating as FAIL")
            return ScoringResult(status="FAIL", score=0.0, reason="scorer returned invalid JSON")

        status = data.get("status", "FAIL")
        score = float(data.get("score", 0.0))
        uncertain_fields = data.get("uncertain_fields", [])
        reason = data.get("reason", "")

        if status not in ("OK", "UNSURE", "FAIL"):
            logger.warning("ConfidenceScorer: unexpected status '%s', defaulting to FAIL", status)
            status = "FAIL"

        logger.debug("ConfidenceScorer: status=%s score=%.2f", status, score)
        return ScoringResult(status=status, score=score, uncertain_fields=uncertain_fields, reason=reason)

    def _call_with_retry(self, user_content: str, max_retries: int = 3) -> str:
        """Call gpt-4o-mini with exponential backoff retry."""
        for attempt in range(max_retries):
            try:
                response = self._client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0,
                    max_tokens=256,
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
