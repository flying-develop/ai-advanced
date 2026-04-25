"""Routed inference pipeline — extends day 7 pipeline with model routing and escalation."""

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Make scripts/ and routing/ importable
_scripts = Path(__file__).parent.parent
_routing = Path(__file__).parent
for _p in [str(_scripts), str(_routing)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from openai import OpenAI

from confidence import ConstraintChecker, ConfidenceScorer
from inference_pipeline import SYSTEM_PROMPT, EXTRACTION_PROMPT
from model_router import ModelRouter
from utils.openai_utils import call_with_retry, strip_json_fences

logger = logging.getLogger(__name__)


@dataclass
class RoutedResult:
    """Full result of processing one vacancy through the routed pipeline."""

    extraction: dict | None
    final_status: str  # "OK" | "FAIL"
    confidence_score: float
    initial_model: str
    escalated: bool
    escalation_reason: str
    tier1_calls: int
    tier2_calls: int
    total_calls: int
    latency_ms: float
    constraint_violations: list[str] = field(default_factory=list)
    constraint_warnings: list[str] = field(default_factory=list)


class RoutedPipeline:
    """Extraction pipeline with model routing and tier escalation.

    Session metrics accumulated:
    - total, ok_count, fail_count
    - tier1_only: processed on gpt-4o-mini only
    - escalated_count: sent to gpt-4o
    - escalated_ok: rescued after escalation
    - escalated_fail: still failed after escalation
    - total_tier1_calls, total_tier2_calls
    - total_latency_ms
    """

    def __init__(self, openai_client: OpenAI) -> None:
        self._client = openai_client
        self.router = ModelRouter()
        self.constraint_checker = ConstraintChecker()
        self.confidence_scorer = ConfidenceScorer(openai_client)

        self.total: int = 0
        self.ok_count: int = 0
        self.fail_count: int = 0
        self.tier1_only: int = 0
        self.escalated_count: int = 0
        self.escalated_ok: int = 0
        self.escalated_fail: int = 0
        self.total_tier1_calls: int = 0
        self.total_tier2_calls: int = 0
        self.total_latency_ms: float = 0.0

    def process(self, vacancy_text: str) -> RoutedResult:
        """Full routing cycle: select model → extract → check → score → escalate if needed."""
        start = time.monotonic()
        tier1_calls = 0
        tier2_calls = 0

        # Step 1: Router selects starting model
        initial_model = self.router.select_initial_model(vacancy_text)
        is_tier1_initial = initial_model == ModelRouter.TIER1_MODEL

        extraction_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": EXTRACTION_PROMPT + vacancy_text},
        ]

        # Step 2: Extraction on initial model
        extraction_raw = call_with_retry(self._client, extraction_messages, model=initial_model)
        if is_tier1_initial:
            tier1_calls += 1
        else:
            tier2_calls += 1

        try:
            extraction = json.loads(strip_json_fences(extraction_raw))
        except json.JSONDecodeError:
            return self._build_result(
                extraction=None,
                final_status="FAIL",
                confidence_score=0.0,
                initial_model=initial_model,
                escalated=False,
                escalation_reason="",
                tier1_calls=tier1_calls,
                tier2_calls=tier2_calls,
                elapsed_ms=(time.monotonic() - start) * 1000,
                violations=[],
                warnings=[],
            )

        # Step 3: Constraint check (no API)
        constraint = self.constraint_checker.check(extraction)
        if constraint.status == "FAIL":
            return self._build_result(
                extraction=None,
                final_status="FAIL",
                confidence_score=0.0,
                initial_model=initial_model,
                escalated=False,
                escalation_reason="",
                tier1_calls=tier1_calls,
                tier2_calls=tier2_calls,
                elapsed_ms=(time.monotonic() - start) * 1000,
                violations=constraint.violations,
                warnings=constraint.warnings,
            )

        # Step 4: Confidence scoring on initial model
        scoring = self.confidence_scorer.score(vacancy_text, extraction, model=initial_model)
        if is_tier1_initial:
            tier1_calls += 1
        else:
            tier2_calls += 1

        # gpt-4o was initial: escalation not possible; UNSURE → OK (gpt-4o is our ceiling)
        if not is_tier1_initial:
            final_status = "FAIL" if scoring.status == "FAIL" else "OK"
            return self._build_result(
                extraction=extraction if final_status == "OK" else None,
                final_status=final_status,
                confidence_score=scoring.score,
                initial_model=initial_model,
                escalated=False,
                escalation_reason="",
                tier1_calls=tier1_calls,
                tier2_calls=tier2_calls,
                elapsed_ms=(time.monotonic() - start) * 1000,
                violations=constraint.violations,
                warnings=constraint.warnings,
            )

        # mini was initial but no escalation needed (OK or FAIL from scorer)
        if not self.router.should_escalate(scoring.score, scoring.status):
            final_status = "OK" if scoring.status == "OK" else "FAIL"
            return self._build_result(
                extraction=extraction if final_status == "OK" else None,
                final_status=final_status,
                confidence_score=scoring.score,
                initial_model=initial_model,
                escalated=False,
                escalation_reason="",
                tier1_calls=tier1_calls,
                tier2_calls=tier2_calls,
                elapsed_ms=(time.monotonic() - start) * 1000,
                violations=constraint.violations,
                warnings=constraint.warnings,
            )

        # Step 5: Escalate to gpt-4o
        escalation_reason = self.router.get_escalation_reason(scoring.score, scoring.status)
        logger.info("Escalating to %s: %s", ModelRouter.TIER2_MODEL, escalation_reason)

        tier2_raw = call_with_retry(
            self._client, extraction_messages, model=ModelRouter.TIER2_MODEL
        )
        tier2_calls += 1

        try:
            tier2_extraction = json.loads(strip_json_fences(tier2_raw))
        except json.JSONDecodeError:
            return self._build_result(
                extraction=None,
                final_status="FAIL",
                confidence_score=0.0,
                initial_model=initial_model,
                escalated=True,
                escalation_reason=escalation_reason,
                tier1_calls=tier1_calls,
                tier2_calls=tier2_calls,
                elapsed_ms=(time.monotonic() - start) * 1000,
                violations=[],
                warnings=[],
            )

        # Step 6: Final constraint check on tier 2 result
        tier2_constraint = self.constraint_checker.check(tier2_extraction)
        if tier2_constraint.status == "FAIL":
            return self._build_result(
                extraction=None,
                final_status="FAIL",
                confidence_score=0.0,
                initial_model=initial_model,
                escalated=True,
                escalation_reason=escalation_reason,
                tier1_calls=tier1_calls,
                tier2_calls=tier2_calls,
                elapsed_ms=(time.monotonic() - start) * 1000,
                violations=tier2_constraint.violations,
                warnings=tier2_constraint.warnings,
            )

        # Confidence scoring on tier 2 result
        tier2_scoring = self.confidence_scorer.score(
            vacancy_text, tier2_extraction, model=ModelRouter.TIER2_MODEL
        )
        tier2_calls += 1

        # gpt-4o is our ceiling: UNSURE → OK, only hard FAIL rejects
        final_status = "FAIL" if tier2_scoring.status == "FAIL" else "OK"
        return self._build_result(
            extraction=tier2_extraction if final_status == "OK" else None,
            final_status=final_status,
            confidence_score=tier2_scoring.score,
            initial_model=initial_model,
            escalated=True,
            escalation_reason=escalation_reason,
            tier1_calls=tier1_calls,
            tier2_calls=tier2_calls,
            elapsed_ms=(time.monotonic() - start) * 1000,
            violations=tier2_constraint.violations,
            warnings=tier2_constraint.warnings,
        )

    def get_metrics(self) -> dict:
        """Return accumulated session metrics."""
        return {
            "total": self.total,
            "ok_count": self.ok_count,
            "fail_count": self.fail_count,
            "tier1_only": self.tier1_only,
            "escalated_count": self.escalated_count,
            "escalated_ok": self.escalated_ok,
            "escalated_fail": self.escalated_fail,
            "total_tier1_calls": self.total_tier1_calls,
            "total_tier2_calls": self.total_tier2_calls,
            "total_calls": self.total_tier1_calls + self.total_tier2_calls,
            "avg_calls": (self.total_tier1_calls + self.total_tier2_calls) / max(self.total, 1),
            "avg_latency_ms": self.total_latency_ms / max(self.total, 1),
        }

    def print_metrics(self) -> None:
        """Print formatted metrics table."""
        m = self.get_metrics()
        total = m["total"] or 1
        ok_pct = m["ok_count"] / total * 100
        fail_pct = m["fail_count"] / total * 100
        tier1_pct = m["tier1_only"] / total * 100
        esc_pct = m["escalated_count"] / total * 100
        esc_ok_pct = m["escalated_ok"] / max(m["escalated_count"], 1) * 100
        avg_latency_s = m["avg_latency_ms"] / 1000

        print("╔══════════════════════════════════════════════════════════════╗")
        print("║              ROUTING REPORT — DAY 8                          ║")
        print("╠══════════════════════════════════════════════════════════════╣")
        print(f"║ Total processed:          {m['total']:<36}║")
        print(f"║ OK:                       {m['ok_count']:<3} ({ok_pct:.0f}%){'':31}║")
        print(f"║ FAIL:                     {m['fail_count']:<3} ({fail_pct:.0f}%){'':31}║")
        print("╠══════════════════════════════════════════════════════════════╣")
        print(f"║ Stayed on gpt-4o-mini:    {m['tier1_only']:<3} ({tier1_pct:.0f}%) — tier1 only{'':17}║")
        print(f"║ Escalated to gpt-4o:      {m['escalated_count']:<3} ({esc_pct:.0f}%){'':31}║")
        print(f"║   └─ rescued after esc.:  {m['escalated_ok']:<3} ({esc_ok_pct:.0f}% of escalated){'':17}║")
        print(f"║   └─ failed after esc.:   {m['escalated_fail']:<36}║")
        print("╠══════════════════════════════════════════════════════════════╣")
        print(f"║ Total API calls:          {m['total_calls']:<36}║")
        print(f"║   Tier 1 (mini) calls:    {m['total_tier1_calls']:<36}║")
        print(f"║   Tier 2 (gpt-4o) calls:  {m['total_tier2_calls']:<36}║")
        print(f"║ Avg calls per request:    {m['avg_calls']:.1f}{'':34}║")
        print(f"║ Avg latency:              {avg_latency_s:.1f}s{'':33}║")
        print("╚══════════════════════════════════════════════════════════════╝")

    def _build_result(
        self,
        extraction: dict | None,
        final_status: str,
        confidence_score: float,
        initial_model: str,
        escalated: bool,
        escalation_reason: str,
        tier1_calls: int,
        tier2_calls: int,
        elapsed_ms: float,
        violations: list[str],
        warnings: list[str],
    ) -> RoutedResult:
        self.total += 1
        self.total_latency_ms += elapsed_ms
        self.total_tier1_calls += tier1_calls
        self.total_tier2_calls += tier2_calls

        if final_status == "OK":
            self.ok_count += 1
        else:
            self.fail_count += 1

        if escalated:
            self.escalated_count += 1
            if final_status == "OK":
                self.escalated_ok += 1
            else:
                self.escalated_fail += 1
        elif initial_model == ModelRouter.TIER1_MODEL:
            self.tier1_only += 1

        return RoutedResult(
            extraction=extraction,
            final_status=final_status,
            confidence_score=confidence_score,
            initial_model=initial_model,
            escalated=escalated,
            escalation_reason=escalation_reason,
            tier1_calls=tier1_calls,
            tier2_calls=tier2_calls,
            total_calls=tier1_calls + tier2_calls,
            latency_ms=elapsed_ms,
            constraint_violations=violations,
            constraint_warnings=warnings,
        )
