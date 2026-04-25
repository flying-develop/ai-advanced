"""Constraint-based validation of extraction results — no API calls required."""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

VALID_LEVELS = {"junior", "middle", "senior", "lead", "unknown"}
VALID_REMOTE = {"true", "false", "hybrid", "unknown"}


@dataclass
class ConstraintResult:
    """Result of constraint-based validation."""

    status: str  # "OK" | "FAIL"
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ConstraintChecker:
    """Validates extraction result without API calls. Always runs first — free and instant."""

    def check(self, extraction: dict) -> ConstraintResult:
        """Return ConstraintResult with status, violations, and warnings."""
        violations: list[str] = []
        warnings: list[str] = []

        level = extraction.get("level")
        if level not in VALID_LEVELS:
            violations.append(f"level '{level}' not in {VALID_LEVELS}")

        remote = extraction.get("remote")
        if remote not in VALID_REMOTE:
            violations.append(f"remote '{remote}' not in {VALID_REMOTE}")

        salary_from = extraction.get("salary_from")
        if salary_from is not None and not isinstance(salary_from, (int, float)):
            violations.append(f"salary_from must be a number or null, got {type(salary_from).__name__}")

        currency = extraction.get("currency")
        if currency is not None and currency != "null" and salary_from is None:
            violations.append("currency is set but salary_from is null — logical contradiction")

        stack = extraction.get("stack")
        if not isinstance(stack, list):
            violations.append(f"stack must be an array, got {type(stack).__name__}")
        elif any(not isinstance(s, str) or s.strip() == "" for s in stack):
            violations.append("stack contains empty or non-string items")

        exp_min = extraction.get("experience_years_min")
        if exp_min is not None:
            if not isinstance(exp_min, (int, float)):
                violations.append(f"experience_years_min must be a number or null, got {type(exp_min).__name__}")
            elif exp_min < 0 or exp_min > 30:
                violations.append(f"experience_years_min={exp_min} out of range [0, 30]")

        # Warnings (non-fatal)
        if isinstance(stack, list) and len(stack) == 0:
            warnings.append("stack is empty array")

        location = extraction.get("location")
        if location is None and remote == "false":
            warnings.append("location is null but remote is 'false' — suspicious")

        title = extraction.get("title")
        if isinstance(title, str) and len(title) < 3:
            warnings.append(f"title '{title}' is shorter than 3 characters")

        exp_required = extraction.get("experience_years_required")
        if exp_required == "unknown":
            warnings.append("experience_years_required is 'unknown'")

        status = "FAIL" if violations else "OK"
        logger.debug("ConstraintCheck: status=%s violations=%d warnings=%d", status, len(violations), len(warnings))
        return ConstraintResult(status=status, violations=violations, warnings=warnings)
