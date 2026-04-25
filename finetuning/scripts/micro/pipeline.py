"""MicroFirstPipeline — local micro-model gate before cloud Stage 2-3."""

import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_scripts = Path(__file__).parent.parent
_multistage = _scripts / "multistage"
_micro = Path(__file__).parent
for _p in [str(_scripts), str(_multistage), str(_micro)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from openai import OpenAI

from confidence import ConstraintChecker
from micro_classifier import MicroClassifier, MicroResult
from stage1_classifier import Stage1Classifier, Stage1Result
from stage2_extractor import Stage2Extractor, Stage2Result
from stage3_normalizer import Stage3Normalizer, Stage3Result

logger = logging.getLogger(__name__)


@dataclass
class MicroFirstResult:
    """Full result of one request through the micro-first pipeline."""

    extraction: dict | None
    final_status: str           # OK | SKIP | UNSURE_ESCALATED | FAIL
    micro_result: MicroResult
    used_cloud_stage1: bool
    cloud_stage1_result: Stage1Result | None
    stage2: Stage2Result | None
    stage3: Stage3Result | None
    total_cloud_calls: int
    total_latency_ms: float
    micro_latency_ms: float
    cloud_latency_ms: float


class MicroFirstPipeline:
    """Pipeline with local micro-model gate. Falls back to MultiStagePipeline if Ollama unavailable.

    Metrics:
    - total, micro_rejected, micro_unsure, micro_passed
    - ok_count, fail_count
    - total_cloud_calls
    - total_micro_latency_ms, total_cloud_latency_ms
    """

    def __init__(self, openai_client: OpenAI, micro_model: str = "qwen2.5:0.5b") -> None:
        self.micro = MicroClassifier(micro_model)
        self._classifier = Stage1Classifier(openai_client)
        self._extractor = Stage2Extractor(openai_client)
        self._normalizer = Stage3Normalizer(openai_client)
        self._constraint_checker = ConstraintChecker()

        self.total: int = 0
        self.micro_rejected: int = 0
        self.micro_unsure: int = 0
        self.micro_passed: int = 0
        self.ok_count: int = 0
        self.fail_count: int = 0
        self.total_cloud_calls: int = 0
        self.total_micro_latency_ms: float = 0.0
        self.total_cloud_latency_ms: float = 0.0

    def process(self, text: str) -> MicroFirstResult:
        """Run micro-first pipeline. Falls back gracefully if Ollama is unavailable."""
        if not self.micro.is_available():
            logger.warning("Ollama unavailable, falling back to MultiStagePipeline")
            return self._fallback_process(text)

        total_start = time.monotonic()

        # Step 1: micro-model
        micro = self.micro.classify(text)
        micro_ms = micro.latency_ms

        cloud_start = time.monotonic()
        cloud_calls = 0

        # Step 2: route based on micro result
        if not micro.is_vacancy and micro.confidence == "OK":
            # Hard reject — no cloud calls
            total_ms = (time.monotonic() - total_start) * 1000
            return self._record(MicroFirstResult(
                extraction=None, final_status="SKIP",
                micro_result=micro, used_cloud_stage1=False,
                cloud_stage1_result=None, stage2=None, stage3=None,
                total_cloud_calls=0, total_latency_ms=total_ms,
                micro_latency_ms=micro_ms, cloud_latency_ms=0.0,
            ), micro_path="rejected")

        if micro.confidence == "UNSURE":
            # Escalate to cloud Stage 1
            s1 = self._classifier.classify(text)
            cloud_calls += 1
            if not s1.is_vacancy:
                cloud_ms = (time.monotonic() - cloud_start) * 1000
                total_ms = (time.monotonic() - total_start) * 1000
                return self._record(MicroFirstResult(
                    extraction=None, final_status="UNSURE_ESCALATED",
                    micro_result=micro, used_cloud_stage1=True,
                    cloud_stage1_result=s1, stage2=None, stage3=None,
                    total_cloud_calls=cloud_calls, total_latency_ms=total_ms,
                    micro_latency_ms=micro_ms, cloud_latency_ms=cloud_ms,
                ), micro_path="unsure")
            # Cloud confirmed vacancy — proceed with s1 result
            stage1_result = s1
        else:
            # micro: is_vacancy=True + confidence=OK → skip cloud Stage 1
            # Build a synthetic Stage1Result from micro output
            stage1_result = Stage1Result(
                is_vacancy=True,
                language="unknown",
                structure_quality=micro.structure_quality,
                reason=micro.reason,
                tokens_used=0,
                latency_ms=0.0,
            )

        # Step 3: Stage 2 + Stage 3
        s2 = self._extractor.extract(text, stage1_result)
        cloud_calls += 1

        s3 = self._normalizer.normalize(s2)
        cloud_calls += 1

        cloud_ms = (time.monotonic() - cloud_start) * 1000
        total_ms = (time.monotonic() - total_start) * 1000

        used_cloud_s1 = micro.confidence == "UNSURE"

        if not s3.extraction:
            return self._record(MicroFirstResult(
                extraction=None, final_status="FAIL",
                micro_result=micro, used_cloud_stage1=used_cloud_s1,
                cloud_stage1_result=stage1_result if used_cloud_s1 else None,
                stage2=s2, stage3=s3,
                total_cloud_calls=cloud_calls, total_latency_ms=total_ms,
                micro_latency_ms=micro_ms, cloud_latency_ms=cloud_ms,
            ), micro_path="passed")

        constraint = self._constraint_checker.check(s3.extraction)
        if constraint.status == "FAIL":
            return self._record(MicroFirstResult(
                extraction=None, final_status="FAIL",
                micro_result=micro, used_cloud_stage1=used_cloud_s1,
                cloud_stage1_result=stage1_result if used_cloud_s1 else None,
                stage2=s2, stage3=s3,
                total_cloud_calls=cloud_calls, total_latency_ms=total_ms,
                micro_latency_ms=micro_ms, cloud_latency_ms=cloud_ms,
            ), micro_path="passed")

        return self._record(MicroFirstResult(
            extraction=s3.extraction, final_status="OK",
            micro_result=micro, used_cloud_stage1=used_cloud_s1,
            cloud_stage1_result=stage1_result if used_cloud_s1 else None,
            stage2=s2, stage3=s3,
            total_cloud_calls=cloud_calls, total_latency_ms=total_ms,
            micro_latency_ms=micro_ms, cloud_latency_ms=cloud_ms,
        ), micro_path="passed")

    def _fallback_process(self, text: str) -> MicroFirstResult:
        """Fallback when Ollama is unavailable: run cloud Stage 1-2-3."""
        from pipeline import MultiStagePipeline  # multistage/pipeline.py is on sys.path
        client = self._classifier._client
        pipeline = MultiStagePipeline(client)  # type: ignore[arg-type]
        mr = pipeline.process(text)

        # Build a dummy MicroResult to satisfy the interface
        dummy_micro = MicroResult(
            is_vacancy=False, structure_quality="low",
            confidence="UNSURE", reason="ollama unavailable",
            latency_ms=0.0, model="unavailable",
        )
        return MicroFirstResult(
            extraction=mr.extraction, final_status=mr.final_status,
            micro_result=dummy_micro, used_cloud_stage1=True,
            cloud_stage1_result=mr.stage1, stage2=mr.stage2, stage3=mr.stage3,
            total_cloud_calls=mr.total_api_calls, total_latency_ms=mr.latency_ms,
            micro_latency_ms=0.0, cloud_latency_ms=mr.latency_ms,
        )

    def get_metrics(self) -> dict:
        """Return accumulated session metrics."""
        total = self.total or 1
        return {
            "total": self.total,
            "micro_rejected": self.micro_rejected,
            "micro_unsure": self.micro_unsure,
            "micro_passed": self.micro_passed,
            "ok_count": self.ok_count,
            "fail_count": self.fail_count,
            "total_cloud_calls": self.total_cloud_calls,
            "avg_cloud_calls": self.total_cloud_calls / total,
            "avg_micro_latency_ms": self.total_micro_latency_ms / total,
            "avg_cloud_latency_ms": self.total_cloud_latency_ms / total,
            "avg_total_latency_ms": (self.total_micro_latency_ms + self.total_cloud_latency_ms) / total,
        }

    def print_metrics(self) -> None:
        """Print table with micro savings breakdown."""
        m = self.get_metrics()
        total = m["total"] or 1
        ok_pct = m["ok_count"] / total * 100
        rej_pct = m["micro_rejected"] / total * 100
        unsure_pct = m["micro_unsure"] / total * 100
        passed_pct = m["micro_passed"] / total * 100
        model = self.micro.model

        print(f"╔══════════════════════════════════════════════════════════╗")
        print(f"║     MICRO-FIRST PIPELINE REPORT ({model:^20}) ║")
        print(f"╠══════════════════════════════════════════════════════════╣")
        print(f"║ Total processed:      {m['total']:<36}║")
        print(f"║ OK:                   {m['ok_count']:<3} ({ok_pct:.0f}%){'':29}║")
        print(f"║ Micro rejected (SKIP):{m['micro_rejected']:<3} ({rej_pct:.0f}%) — 0 cloud calls{'':11}║")
        print(f"║ Micro UNSURE:         {m['micro_unsure']:<3} ({unsure_pct:.0f}%) — escalated to cloud S1{'':5}║")
        print(f"║ Micro passed OK:      {m['micro_passed']:<3} ({passed_pct:.0f}%) — skipped cloud S1{'':8}║")
        print(f"╠══════════════════════════════════════════════════════════╣")
        print(f"║ Total cloud calls:    {m['total_cloud_calls']:<36}║")
        print(f"║ Avg cloud calls:      {m['avg_cloud_calls']:.1f}{'':35}║")
        print(f"║ Avg micro latency:    {m['avg_micro_latency_ms']:.0f}ms{'':33}║")
        print(f"║ Avg cloud latency:    {m['avg_cloud_latency_ms']:.0f}ms{'':33}║")
        print(f"╚══════════════════════════════════════════════════════════╝")

    def _record(self, result: MicroFirstResult, micro_path: str) -> MicroFirstResult:
        self.total += 1
        self.total_cloud_calls += result.total_cloud_calls
        self.total_micro_latency_ms += result.micro_latency_ms
        self.total_cloud_latency_ms += result.cloud_latency_ms

        if micro_path == "rejected":
            self.micro_rejected += 1
        elif micro_path == "unsure":
            self.micro_unsure += 1
        else:
            self.micro_passed += 1

        if result.final_status == "OK":
            self.ok_count += 1
        elif result.final_status in ("FAIL",):
            self.fail_count += 1

        return result
