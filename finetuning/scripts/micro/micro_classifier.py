"""Local micro-model classifier via Ollama HTTP API — no cloud calls."""

import json
import logging
import time
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
You are a text classifier. Determine if the text is a job vacancy posting.

Text:
{text}

Reply with JSON only:
{{
  "is_vacancy": true or false,
  "structure_quality": "high" or "medium" or "low",
  "confidence": "OK" or "UNSURE",
  "reason": "one short sentence"
}}

confidence=UNSURE if: text is borderline, very short, or you are not certain."""


@dataclass
class MicroResult:
    """Result from local micro-model classification."""

    is_vacancy: bool
    structure_quality: str   # high | medium | low
    confidence: str          # OK | UNSURE
    reason: str
    latency_ms: float
    model: str


class MicroClassifier:
    """Local classifier via Ollama HTTP API. Uses /api/generate, no openai SDK."""

    def __init__(self, model: str = "qwen2.5:0.5b") -> None:
        self.model = model
        self.base_url = "http://localhost:11434"

    def classify(self, text: str) -> MicroResult:
        """Return MicroResult. confidence=UNSURE when model is not certain."""
        start = time.monotonic()
        # Truncate to 500 chars — micro-model only needs to detect vacancy type
        snippet = (text or "(empty)")[:500]
        prompt = _PROMPT_TEMPLATE.format(text=snippet)

        for attempt in range(2):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 80},
                    },
                    timeout=600,
                )
                resp.raise_for_status()
                raw = resp.json().get("response", "")
                break
            except requests.RequestException as e:
                if attempt == 1:
                    elapsed = (time.monotonic() - start) * 1000
                    logger.warning("Ollama request failed: %s", e)
                    return MicroResult(
                        is_vacancy=False, structure_quality="low",
                        confidence="UNSURE", reason=f"request error: {e}",
                        latency_ms=elapsed, model=self.model,
                    )
                logger.warning("Ollama attempt %d failed: %s", attempt + 1, e)

        elapsed = (time.monotonic() - start) * 1000

        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Micro: response not valid JSON: %r", raw[:80])
            return MicroResult(
                is_vacancy=False, structure_quality="low",
                confidence="UNSURE", reason="json parse error",
                latency_ms=elapsed, model=self.model,
            )

        quality = data.get("structure_quality", "low")
        if quality not in ("high", "medium", "low"):
            quality = "low"
        confidence = data.get("confidence", "UNSURE")
        if confidence not in ("OK", "UNSURE"):
            confidence = "UNSURE"

        return MicroResult(
            is_vacancy=bool(data.get("is_vacancy", False)),
            structure_quality=quality,
            confidence=confidence,
            reason=data.get("reason", ""),
            latency_ms=elapsed,
            model=self.model,
        )

    def is_available(self) -> bool:
        """Check that Ollama is running and the model is available."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return any(m == self.model or m.startswith(self.model.split(":")[0]) for m in models)
        except requests.RequestException:
            return False
