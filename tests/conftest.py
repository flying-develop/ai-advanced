"""Shared pytest fixtures for the test suite."""

# stdlib — set env vars BEFORE any src imports so pydantic-settings picks them up
import os

os.environ.setdefault("BOT_TOKEN", "test-bot-token:TEST")
os.environ.setdefault("ALLOWED_USER_ID", "12345")
os.environ.setdefault("QWEN_API_KEY", "test-qwen-key")
os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

from typing import AsyncGenerator
from unittest.mock import AsyncMock

# third-party
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# local
from src.models.base import Base
from src.repositories.conversation_repo import ConversationRepository
from src.services.conversation_service import ConversationService
from src.services.llm_service import LLMService

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def engine():
    """Create an isolated in-memory SQLite engine per test."""
    _engine = create_async_engine(TEST_DB_URL, echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    await _engine.dispose()


@pytest.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a session that is rolled back after each test for isolation."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess
        await sess.rollback()


@pytest.fixture
def conversation_repo(session: AsyncSession) -> ConversationRepository:
    """ConversationRepository backed by the test session."""
    return ConversationRepository(session)


@pytest.fixture
def mock_llm_service() -> AsyncMock:
    """LLMService mock — never touches the real Qwen API."""
    mock = AsyncMock(spec=LLMService)
    mock.complete.return_value = "Mocked AI response"
    return mock


@pytest.fixture
def conversation_service(
    mock_llm_service: AsyncMock,
    conversation_repo: ConversationRepository,
) -> ConversationService:
    """ConversationService wired to an in-memory DB and a mocked LLM."""
    return ConversationService(
        llm_service=mock_llm_service,
        conversation_repo=conversation_repo,
    )
