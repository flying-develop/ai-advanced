"""Multi-stage inference pipeline: Stage 1 classify → Stage 2 extract → Stage 3 normalize."""

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

from confidence import ConstraintChecker
from stage1_classifier import Stage1Classifier, Stage1Result
from stage2_extractor import Stage2Extractor, Stage2Result
from stage3_normalizer import Stage3Normalizer, Stage3Result

logger = logging.getLogger(__name__)


@dataclass
class MultiStageResult:
    """Full result of processing one vacancy through the multi-stage pipeline."""

    extraction: dict | None
    final_status: str    # "OK" | "SKIP" | "FAIL"
    skip_reason: str     # non-empty only when SKIP
    stage1: Stage1Result | None
    stage2: Stage2Result | None
    stage3: Stage3Result | None
    total_tokens: int
    total_api_calls: int
    latency_ms: float
    constraint_violations: list[str]
    constraint_warnings: list[str]


class MultiStagePipeline:
    """Three-stage pipeline with session-level metrics.

    Metrics accumulated:
    - total, ok_count, skip_count, fail_count
    - total_tokens, total_api_calls, total_latency_ms
    - total_constraint_violations
    """

    def __init__(self, client: OpenAI) -> None:
        self._classifier = Stage1Classifier(client)
        self._extractor = Stage2Extractor(client)
        self._normalizer = Stage3Normalizer(client)
        self._constraint_checker = ConstraintChecker()

        self.total: int = 0
        self.ok_count: int = 0
        self.skip_count: int = 0
        self.fail_count: int = 0
        self.total_tokens: int = 0
        self.total_api_calls: int = 0
        self.total_latency_ms: float = 0.0
        self.total_constraint_violations: int = 0

    def process(self, text: str) -> MultiStageResult:
        """Run full multi-stage pipeline. Updates session metrics."""
        start = time.monotonic()
        tokens = 0
        calls = 0

        # Stage 1: classify
        s1 = self._classifier.classify(text)
        tokens += s1.tokens_used
        calls += 1

        if not s1.is_vacancy:
            elapsed = (time.monotonic() - start) * 1000
            return self._record(
                MultiStageResult(
                    extraction=None, final_status="SKIP", skip_reason="not_vacancy",
                    stage1=s1, stage2=None, stage3=None,
                    total_tokens=tokens, total_api_calls=calls, latency_ms=elapsed,
                    constraint_violations=[], constraint_warnings=[],
                )
            )

        # Stage 2: raw extraction
        s2 = self._extractor.extract(text, s1)
        tokens += s2.tokens_used
        calls += 1

        # Stage 3: normalization
        s3 = self._normalizer.normalize(s2)
        tokens += s3.tokens_used
        calls += 1

        # Constraint check (no API)
        if not s3.extraction:
            elapsed = (time.monotonic() - start) * 1000
            return self._record(
                MultiStageResult(
                    extraction=None, final_status="FAIL", skip_reason="",
                    stage1=s1, stage2=s2, stage3=s3,
                    total_tokens=tokens, total_api_calls=calls, latency_ms=elapsed,
                    constraint_violations=["stage3 returned empty extraction"],
                    constraint_warnings=[],
                )
            )

        constraint = self._constraint_checker.check(s3.extraction)
        elapsed = (time.monotonic() - start) * 1000

        if constraint.status == "FAIL":
            return self._record(
                MultiStageResult(
                    extraction=None, final_status="FAIL", skip_reason="",
                    stage1=s1, stage2=s2, stage3=s3,
                    total_tokens=tokens, total_api_calls=calls, latency_ms=elapsed,
                    constraint_violations=constraint.violations,
                    constraint_warnings=constraint.warnings,
                )
            )

        return self._record(
            MultiStageResult(
                extraction=s3.extraction, final_status="OK", skip_reason="",
                stage1=s1, stage2=s2, stage3=s3,
                total_tokens=tokens, total_api_calls=calls, latency_ms=elapsed,
                constraint_violations=constraint.violations,
                constraint_warnings=constraint.warnings,
            )
        )

    def get_metrics(self) -> dict:
        """Return accumulated session metrics."""
        total = self.total or 1
        return {
            "total": self.total,
            "ok_count": self.ok_count,
            "skip_count": self.skip_count,
            "fail_count": self.fail_count,
            "total_tokens": self.total_tokens,
            "total_api_calls": self.total_api_calls,
            "avg_calls": self.total_api_calls / total,
            "avg_tokens": self.total_tokens / total,
            "avg_latency_ms": self.total_latency_ms / total,
            "total_constraint_violations": self.total_constraint_violations,
        }

    def print_metrics(self) -> None:
        """Print formatted metrics table."""
        m = self.get_metrics()
        total = m["total"] or 1
        ok_pct = m["ok_count"] / total * 100
        skip_pct = m["skip_count"] / total * 100
        fail_pct = m["fail_count"] / total * 100
        avg_latency_s = m["avg_latency_ms"] / 1000

        print("╔══════════════════════════════════════════════════════════╗")
        print("║           MULTI-STAGE PIPELINE REPORT — DAY 9            ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"║ Total processed:        {m['total']:<34}║")
        print(f"║ OK:                     {m['ok_count']:<3} ({ok_pct:.0f}%){'':27}║")
        print(f"║ SKIP:                   {m['skip_count']:<3} ({skip_pct:.0f}%) — not vacancy{'':16}║")
        print(f"║ FAIL:                   {m['fail_count']:<3} ({fail_pct:.0f}%){'':27}║")
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"║ Total API calls:        {m['total_api_calls']:<34}║")
        print(f"║ Avg calls per request:  {m['avg_calls']:.1f}{'':32}║")
        print(f"║ Total tokens:           {m['total_tokens']:<34}║")
        print(f"║ Avg tokens per request: {m['avg_tokens']:.0f}{'':32}║")
        print(f"║ Avg latency:            {avg_latency_s:.1f}s{'':31}║")
        print("╚══════════════════════════════════════════════════════════╝")

    def _record(self, result: MultiStageResult) -> MultiStageResult:
        self.total += 1
        self.total_tokens += result.total_tokens
        self.total_api_calls += result.total_api_calls
        self.total_latency_ms += result.latency_ms
        self.total_constraint_violations += len(result.constraint_violations)

        if result.final_status == "OK":
            self.ok_count += 1
        elif result.final_status == "SKIP":
            self.skip_count += 1
        else:
            self.fail_count += 1

        return result
