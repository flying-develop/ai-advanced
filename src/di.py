"""Dependency injection factory — wires together session_pool and services."""

# stdlib
import logging
from typing import AsyncGenerator

# third-party
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# local
from src.config import settings
from src.models.base import Base
from src.repositories.conversation_repo import ConversationRepository
from src.services.conversation_service import ConversationService
from src.services.indirect_injection.agents import (
    DocumentAnalystAgent,
    EmailSummarizerAgent,
    WebSearchAgent,
)
from src.services.indirect_injection.demo_runner import IndirectInjectionDemoRunner
from src.services.indirect_injection.output_validator import OutputValidator
from src.services.indirect_injection.sanitizer import InputSanitizer
from src.services.injection_guard import (
    InjectionGuard,
    SYSTEM_PROMPT_HARDENED,
    SYSTEM_PROMPT_WEAK,
)
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


def build_session_pool() -> async_sessionmaker[AsyncSession]:
    """Create the SQLAlchemy async engine and return a session factory."""
    engine = create_async_engine(
        settings.db_url,
        echo=False,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


def build_llm_service() -> LLMService:
    """Instantiate LLMService with the appropriate system prompt based on protection config."""
    system_prompt = (
        SYSTEM_PROMPT_HARDENED
        if settings.injection_protection_enabled
        else SYSTEM_PROMPT_WEAK
    )
    return LLMService(
        api_key=settings.qwen_api_key,
        model=settings.llm_model,
        base_url=settings.qwen_base_url,
        system_prompt=system_prompt,
    )


def build_injection_guard() -> InjectionGuard | None:
    """Return an InjectionGuard when protection is enabled, None otherwise."""
    if settings.injection_protection_enabled:
        return InjectionGuard()
    return None


def build_indirect_demo_runner() -> IndirectInjectionDemoRunner | None:
    """Return IndirectInjectionDemoRunner when indirect_demo_enabled=True, None otherwise."""
    if not settings.indirect_demo_enabled:
        return None
    email_agent = EmailSummarizerAgent(LLMService(system_prompt=EmailSummarizerAgent.SYSTEM_PROMPT))
    doc_agent = DocumentAnalystAgent(LLMService(system_prompt=DocumentAnalystAgent.SYSTEM_PROMPT))
    web_agent = WebSearchAgent(LLMService(system_prompt=WebSearchAgent.SYSTEM_PROMPT))
    return IndirectInjectionDemoRunner(
        email_agent=email_agent,
        doc_agent=doc_agent,
        web_agent=web_agent,
        sanitizer=InputSanitizer(),
        validator=OutputValidator(),
    )


def build_conversation_service(
    session: AsyncSession,
    llm_service: LLMService,
    injection_guard: InjectionGuard | None,
) -> ConversationService:
    """Build a ConversationService for a single request (one DB session)."""
    repo = ConversationRepository(session=session)
    return ConversationService(
        llm_service=llm_service,
        conversation_repo=repo,
        injection_guard=injection_guard,
    )
