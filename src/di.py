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
    """Instantiate the LLMService with settings from config."""
    return LLMService(
        api_key=settings.qwen_api_key,
        model=settings.llm_model,
        base_url=settings.qwen_base_url,
    )


def build_conversation_service(
    session: AsyncSession,
    llm_service: LLMService,
) -> ConversationService:
    """Build a ConversationService for a single request (one DB session)."""
    repo = ConversationRepository(session=session)
    return ConversationService(llm_service=llm_service, conversation_repo=repo)
