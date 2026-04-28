"""Orchestrates the full indirect injection demo: attack → defend → compare."""

# stdlib
import logging
from dataclasses import dataclass, field

# local
from src.services.indirect_injection.agents import (
    DocumentAnalystAgent,
    EmailSummarizerAgent,
    WebSearchAgent,
)
from src.services.indirect_injection.attack_payloads import (
    make_attack_document_zwsp,
    make_attack_email_html_comment,
    make_attack_webpage_css,
)
from src.services.indirect_injection.boundary import ContentType, wrap_with_boundary
from src.services.indirect_injection.output_validator import OutputValidator
from src.services.indirect_injection.sanitizer import InputSanitizer

logger = logging.getLogger(__name__)


@dataclass
class ScenarioResult:
    """Result of running one attack scenario with and without defenses."""

    scenario_name: str
    vector: str
    unprotected_response: str
    protected_response: str
    attack_succeeded_unprotected: bool
    attack_succeeded_protected: bool
    defense_layers_applied: list[str] = field(default_factory=list)
    output_violations_unprotected: list[str] = field(default_factory=list)
    output_violations_protected: list[str] = field(default_factory=list)


class IndirectInjectionDemoRunner:
    """Run all 3 indirect injection scenarios with and without defenses."""

    def __init__(
        self,
        email_agent: EmailSummarizerAgent,
        doc_agent: DocumentAnalystAgent,
        web_agent: WebSearchAgent,
        sanitizer: InputSanitizer,
        validator: OutputValidator,
    ) -> None:
        self._email_agent = email_agent
        self._doc_agent = doc_agent
        self._web_agent = web_agent
        self._sanitizer = sanitizer
        self._validator = validator

    async def run_all(self) -> list[ScenarioResult]:
        """Run all 3 scenarios and return structured results."""
        results = []
        results.append(await self._run_email_scenario())
        results.append(await self._run_document_scenario())
        results.append(await self._run_web_scenario())
        return results

    async def _run_email_scenario(self) -> ScenarioResult:
        raw = make_attack_email_html_comment()

        unprotected = await self._email_agent.summarize(raw)
        unprotected_violations = self._validator.validate(unprotected, 'email').violations

        sanitized = self._sanitizer.sanitize_email(raw)
        bounded = wrap_with_boundary(sanitized, ContentType.EMAIL)
        protected = await self._email_agent.summarize(bounded)
        protected_violations = self._validator.validate(protected, 'email').violations

        logger.info(
            "Email scenario — unprotected violations: %d, protected violations: %d",
            len(unprotected_violations),
            len(protected_violations),
        )
        return ScenarioResult(
            scenario_name='Email HTML Comment Injection',
            vector='html_comment',
            unprotected_response=unprotected,
            protected_response=protected,
            attack_succeeded_unprotected=bool(unprotected_violations),
            attack_succeeded_protected=bool(protected_violations),
            defense_layers_applied=[
                'HTML comment stripping',
                'Content boundary markers',
                'Output validation',
            ],
            output_violations_unprotected=unprotected_violations,
            output_violations_protected=protected_violations,
        )

    async def _run_document_scenario(self) -> ScenarioResult:
        raw = make_attack_document_zwsp()
        question = "What is the net profit margin for Q1 2024?"

        unprotected = await self._doc_agent.analyze(raw, question)
        unprotected_violations = self._validator.validate(unprotected, 'document').violations

        sanitized = self._sanitizer.sanitize_document(raw)
        bounded = wrap_with_boundary(sanitized, ContentType.DOCUMENT)
        protected = await self._doc_agent.analyze(bounded, question)
        protected_violations = self._validator.validate(protected, 'document').violations

        logger.info(
            "Document scenario — unprotected violations: %d, protected violations: %d",
            len(unprotected_violations),
            len(protected_violations),
        )
        return ScenarioResult(
            scenario_name='Document Zero-Width Character Injection',
            vector='zero_width',
            unprotected_response=unprotected,
            protected_response=protected,
            attack_succeeded_unprotected=bool(unprotected_violations),
            attack_succeeded_protected=bool(protected_violations),
            defense_layers_applied=[
                'Zero-width character stripping',
                'Unicode NFKC normalization',
                'Content boundary markers',
                'Output validation',
            ],
            output_violations_unprotected=unprotected_violations,
            output_violations_protected=protected_violations,
        )

    async def _run_web_scenario(self) -> ScenarioResult:
        raw = make_attack_webpage_css()

        unprotected = await self._web_agent.extract(raw)
        unprotected_violations = (
            self._validator.validate(unprotected, 'web').violations
            + self._validator.validate_pricing(unprotected).violations
        )

        sanitized = self._sanitizer.sanitize_html(raw)
        bounded = wrap_with_boundary(sanitized, ContentType.WEBPAGE)
        protected = await self._web_agent.extract(bounded)
        protected_violations = (
            self._validator.validate(protected, 'web').violations
            + self._validator.validate_pricing(protected).violations
        )

        logger.info(
            "Web scenario — unprotected violations: %d, protected violations: %d",
            len(unprotected_violations),
            len(protected_violations),
        )
        return ScenarioResult(
            scenario_name='Web Page CSS-Hidden Text Injection',
            vector='css_hidden',
            unprotected_response=unprotected,
            protected_response=protected,
            attack_succeeded_unprotected=bool(unprotected_violations),
            attack_succeeded_protected=bool(protected_violations),
            defense_layers_applied=[
                'HTML visible-text extraction',
                'CSS hiding pattern removal',
                'Content boundary markers',
                'Pricing output validation',
            ],
            output_violations_unprotected=unprotected_violations,
            output_violations_protected=protected_violations,
        )
