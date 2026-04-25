"""Model router — selects starting model and escalation policy based on heuristics."""

import logging
import re

logger = logging.getLogger(__name__)


class ModelRouter:
    """Determines starting model and escalation thresholds.

    Starting model heuristics:
    1. Text length < 100 chars → gpt-4o (too little data for mini to be reliable)
    2. Mixed language in first 200 chars → gpt-4o
    3. Default → gpt-4o-mini

    Escalation policy:
    - confidence score < 0.75 → escalate to gpt-4o
    - status UNSURE → escalate
    - status FAIL → reject, do not escalate
    """

    TIER1_MODEL = "gpt-4o-mini"
    TIER2_MODEL = "gpt-4o"
    ESCALATION_THRESHOLD = 0.75

    def select_initial_model(self, vacancy_text: str) -> str:
        """Return model name for the first request. Logs selection reason."""
        if len(vacancy_text) < 100:
            logger.info(
                "Router: %s — text too short (%d chars)", self.TIER2_MODEL, len(vacancy_text)
            )
            return self.TIER2_MODEL

        if self._is_mixed_language(vacancy_text):
            logger.info("Router: %s — mixed language detected", self.TIER2_MODEL)
            return self.TIER2_MODEL

        logger.info("Router: %s — default", self.TIER1_MODEL)
        return self.TIER1_MODEL

    def should_escalate(self, score: float, status: str) -> bool:
        """True if result should be escalated to Tier 2."""
        if status == "FAIL":
            return False
        return status == "UNSURE" or score < self.ESCALATION_THRESHOLD

    def get_escalation_reason(self, score: float, status: str) -> str:
        """Human-readable escalation reason for logs and reports."""
        if status == "UNSURE":
            return f"UNSURE score={score:.2f}"
        if score < self.ESCALATION_THRESHOLD:
            return f"low confidence score={score:.2f}"
        return ""

    def _is_mixed_language(self, text: str) -> bool:
        """True if first 200 chars contain significant amounts of both Cyrillic and Latin."""
        sample = text[:200]
        cyrillic = len(re.findall(r"[а-яёА-ЯЁ]", sample))
        latin = len(re.findall(r"[a-zA-Z]", sample))
        total = cyrillic + latin
        if total < 20:
            return False
        latin_ratio = latin / total
        cyrillic_ratio = cyrillic / total
        # 0.30 false-positives on Russian text with English tech terms (~35% Latin)
        return latin_ratio > 0.40 and cyrillic_ratio > 0.40
