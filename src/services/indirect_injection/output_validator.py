"""Defense Layer 3 — output validator that detects signs of successful injection."""

# stdlib
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of an output validation check."""

    is_valid: bool
    violations: list[str] = field(default_factory=list)

    @property
    def violation_summary(self) -> str:
        """Human-readable summary of violations."""
        return '; '.join(self.violations) if self.violations else 'none'


class OutputValidator:
    """Defense Layer 3: validate agent output for signs of successful injection."""

    _SUSPICIOUS_OUTPUT_PATTERNS = [
        (
            r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
            'email address in output (possible exfiltration)',
        ),
        (
            r'(?i)(forward|send|email|отправь|перешли).{0,50}@',
            'forwarding instruction in output',
        ),
        (
            r'(?i)(ignore|forget|забудь).{0,30}(instruction|prompt|инструкци)',
            'instruction-override in output',
        ),
        (
            r'(?i)(system override|system message|agent instruction)',
            'meta-instruction leaked into output',
        ),
        (
            r'(?i)(i am now|я теперь).{0,30}(unrestricted|без ограничений|free)',
            'identity compromise in output',
        ),
    ]

    _COMPILED = [
        (re.compile(p, re.IGNORECASE | re.DOTALL), label)
        for p, label in _SUSPICIOUS_OUTPUT_PATTERNS
    ]

    def validate(self, output: str, agent_type: str) -> ValidationResult:
        """Check agent output for generic injection indicators."""
        violations = []
        for pattern, label in self._COMPILED:
            if pattern.search(output):
                violations.append(f"[{agent_type}] {label}")
        return ValidationResult(is_valid=len(violations) == 0, violations=violations)

    def validate_pricing(self, output: str) -> ValidationResult:
        """Check web agent output for pricing disinformation (override to free/zero)."""
        violations = []
        if re.search(r'(?i)(free|бесплатно|\$0|zero cost)', output):
            if not re.search(r'\$[1-9][0-9]+', output):
                violations.append('pricing overridden to free without original price')
        return ValidationResult(is_valid=len(violations) == 0, violations=violations)
