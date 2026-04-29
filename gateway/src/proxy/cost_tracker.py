"""Token cost calculation and running totals for LLM requests."""

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

PRICING: dict[str, dict[str, float]] = {
    # Anthropic
    "claude-haiku-4-5-20251001": {"input_per_1m": 0.80, "output_per_1m": 4.00},
    "claude-sonnet-4-20250514": {"input_per_1m": 3.00, "output_per_1m": 15.00},
    # OpenAI
    "gpt-4o": {"input_per_1m": 2.50, "output_per_1m": 10.00},
    "gpt-4o-mini": {"input_per_1m": 0.15, "output_per_1m": 0.60},
    "gpt-4-turbo": {"input_per_1m": 10.00, "output_per_1m": 30.00},
    "o3-mini": {"input_per_1m": 1.10, "output_per_1m": 4.40},
    "o4-mini": {"input_per_1m": 1.10, "output_per_1m": 4.40},
}

# Keep old name as alias for backward compatibility
ANTHROPIC_PRICING = PRICING

_FALLBACK_MODEL = "claude-haiku-4-5-20251001"


class CostTracker:
    """Calculates per-request costs and accumulates totals using Decimal to avoid float drift."""

    def __init__(self) -> None:
        self._total_cost: Decimal = Decimal("0")
        self._total_requests: int = 0

    @staticmethod
    def calculate(model: str, input_tokens: int, output_tokens: int) -> float:
        """Return cost in USD for the given model and token counts."""
        pricing = PRICING.get(model)
        if pricing is None:
            logger.warning("Unknown model '%s' — using Haiku pricing as fallback.", model)
            pricing = ANTHROPIC_PRICING[_FALLBACK_MODEL]

        cost = Decimal(str(input_tokens)) * Decimal(str(pricing["input_per_1m"])) / Decimal("1_000_000")
        cost += Decimal(str(output_tokens)) * Decimal(str(pricing["output_per_1m"])) / Decimal("1_000_000")
        return float(cost)

    def add(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost, add to running total, and return the per-request cost."""
        cost = self.calculate(model, input_tokens, output_tokens)
        self._total_cost += Decimal(str(cost))
        self._total_requests += 1
        return cost

    def total_cost(self) -> float:
        """Return accumulated cost in USD as float."""
        return float(self._total_cost)

    def total_requests(self) -> int:
        """Return total number of tracked requests."""
        return self._total_requests
