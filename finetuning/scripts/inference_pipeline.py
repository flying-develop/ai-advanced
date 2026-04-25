"""Full inference pipeline: extraction + constraint check + confidence scoring + self-check."""

import json
import logging
import time
from dataclasses import dataclass, field

from openai import OpenAI

from confidence import ConstraintChecker, ConfidenceScorer, SelfChecker
from utils.openai_utils import call_with_retry

logger = logging.getLogger(__name__)

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
class PipelineResult:
    """Full result of processing one vacancy through the pipeline."""

    extraction: dict | None
    final_status: str  # "OK" | "UNSURE" | "FAIL"
    confidence_score: float
    constraint_violations: list[str] = field(default_factory=list)
    constraint_warnings: list[str] = field(default_factory=list)
    uncertain_fields: list[str] = field(default_factory=list)
    self_check_triggered: bool = False
    api_calls_made: int = 0
    latency_ms: float = 0.0
    reason: str = ""


class InferencePipeline:
    """Extraction + confidence control pipeline with session-level metrics."""

    def __init__(self, client: OpenAI) -> None:
        self._client = client
        self._constraint_checker = ConstraintChecker()
        self._confidence_scorer = ConfidenceScorer(client)
        self._self_checker = SelfChecker(client)

        self.total: int = 0
        self.ok_count: int = 0
        self.unsure_count: int = 0
        self.fail_count: int = 0
        self.self_check_triggered: int = 0
        self.self_check_rescued: int = 0
        self.total_api_calls: int = 0
        self.total_latency_ms: float = 0.0

    def process(self, vacancy_text: str) -> PipelineResult:
        """Run full pipeline and return PipelineResult. Updates session metrics."""
        start = time.monotonic()
        api_calls = 0

        # Step 1: Extraction
        extraction_raw = self._extract_with_retry(vacancy_text)
        api_calls += 1

        try:
            extraction = json.loads(extraction_raw)
        except json.JSONDecodeError:
            elapsed = (time.monotonic() - start) * 1000
            self._update_metrics("FAIL", api_calls, elapsed, self_check=False, rescued=False)
            return PipelineResult(
                extraction=None,
                final_status="FAIL",
                confidence_score=0.0,
                api_calls_made=api_calls,
                latency_ms=elapsed,
                reason="extraction returned invalid JSON",
            )

        # Step 2: Constraint check (no API)
        constraint_result = self._constraint_checker.check(extraction)
        if constraint_result.status == "FAIL":
            elapsed = (time.monotonic() - start) * 1000
            self._update_metrics("FAIL", api_calls, elapsed, self_check=False, rescued=False)
            return PipelineResult(
                extraction=None,
                final_status="FAIL",
                confidence_score=0.0,
                constraint_violations=constraint_result.violations,
                constraint_warnings=constraint_result.warnings,
                api_calls_made=api_calls,
                latency_ms=elapsed,
                reason="constraint violation: " + "; ".join(constraint_result.violations),
            )

        # Step 3: Confidence scoring
        scoring_result = self._confidence_scorer.score(vacancy_text, extraction)
        api_calls += 1

        if scoring_result.status == "OK":
            elapsed = (time.monotonic() - start) * 1000
            self._update_metrics("OK", api_calls, elapsed, self_check=False, rescued=False)
            return PipelineResult(
                extraction=extraction,
                final_status="OK",
                confidence_score=scoring_result.score,
                constraint_violations=constraint_result.violations,
                constraint_warnings=constraint_result.warnings,
                uncertain_fields=scoring_result.uncertain_fields,
                api_calls_made=api_calls,
                latency_ms=elapsed,
                reason=scoring_result.reason,
            )

        if scoring_result.status == "FAIL":
            elapsed = (time.monotonic() - start) * 1000
            self._update_metrics("FAIL", api_calls, elapsed, self_check=False, rescued=False)
            return PipelineResult(
                extraction=None,
                final_status="FAIL",
                confidence_score=scoring_result.score,
                constraint_violations=constraint_result.violations,
                constraint_warnings=constraint_result.warnings,
                uncertain_fields=scoring_result.uncertain_fields,
                api_calls_made=api_calls,
                latency_ms=elapsed,
                reason=scoring_result.reason,
            )

        # Step 5: UNSURE → self-check
        self_check_result = self._self_checker.check(vacancy_text, extraction)
        api_calls += 1
        rescued = self_check_result.final_status == "OK"

        final_status = self_check_result.final_status
        final_extraction = self_check_result.merged_extraction if rescued else None

        elapsed = (time.monotonic() - start) * 1000
        self._update_metrics(final_status, api_calls, elapsed, self_check=True, rescued=rescued)

        reason = scoring_result.reason
        if rescued:
            reason += " (self-check → OK)"
        else:
            reason += " (self-check → FAIL)"

        return PipelineResult(
            extraction=final_extraction,
            final_status=final_status,
            confidence_score=scoring_result.score,
            constraint_violations=constraint_result.violations,
            constraint_warnings=constraint_result.warnings,
            uncertain_fields=scoring_result.uncertain_fields,
            self_check_triggered=True,
            api_calls_made=api_calls,
            latency_ms=elapsed,
            reason=reason,
        )

    def get_metrics(self) -> dict:
        """Return accumulated session metrics."""
        avg_calls = self.total_api_calls / self.total if self.total else 0.0
        avg_latency = self.total_latency_ms / self.total if self.total else 0.0
        return {
            "total": self.total,
            "ok_count": self.ok_count,
            "unsure_count": self.unsure_count,
            "fail_count": self.fail_count,
            "self_check_triggered": self.self_check_triggered,
            "self_check_rescued": self.self_check_rescued,
            "total_api_calls": self.total_api_calls,
            "avg_calls_per_request": avg_calls,
            "avg_latency_ms": avg_latency,
        }

    def print_metrics(self) -> None:
        """Print formatted metrics table to console."""
        m = self.get_metrics()
        total = m["total"] or 1
        ok_pct = m["ok_count"] / total * 100
        unsure_pct = m["unsure_count"] / total * 100
        fail_pct = m["fail_count"] / total * 100
        avg_latency_s = m["avg_latency_ms"] / 1000

        print("╔══════════════════════════════════════════════════════════╗")
        print("║              INFERENCE QUALITY REPORT — DAY 7            ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"║ Total processed:        {m['total']:<34}║")
        print(f"║ OK:                     {m['ok_count']:<3} ({ok_pct:.0f}%){'':<27}║")
        print(f"║ UNSURE:                 {m['unsure_count']:<3} ({unsure_pct:.0f}%){'':<27}║")
        print(f"║ FAIL:                   {m['fail_count']:<3} ({fail_pct:.0f}%){'':<27}║")
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"║ Self-check triggered:   {m['self_check_triggered']:<34}║")
        print(f"║ Self-check rescued:     {m['self_check_rescued']:<3} (UNSURE→OK){'':<23}║")
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"║ Total API calls:        {m['total_api_calls']:<34}║")
        print(f"║ Avg calls per request:  {m['avg_calls_per_request']:<.1f}{'':<32}║")
        print(f"║ Avg latency:            {avg_latency_s:<.1f}s{'':<31}║")
        print("╚══════════════════════════════════════════════════════════╝")

    def _update_metrics(
        self, status: str, api_calls: int, latency_ms: float, self_check: bool, rescued: bool
    ) -> None:
        self.total += 1
        self.total_api_calls += api_calls
        self.total_latency_ms += latency_ms
        if status == "OK":
            self.ok_count += 1
        elif status == "UNSURE":
            self.unsure_count += 1
        else:
            self.fail_count += 1
        if self_check:
            self.self_check_triggered += 1
        if rescued:
            self.self_check_rescued += 1

    def _extract_with_retry(self, vacancy_text: str, max_retries: int = 3) -> str:
        """Call gpt-4o-mini for extraction with exponential backoff retry."""
        return call_with_retry(
            self._client,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": EXTRACTION_PROMPT + vacancy_text},
            ],
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=512,
            max_retries=max_retries,
        )
