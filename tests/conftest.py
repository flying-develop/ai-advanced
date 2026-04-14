"""Shared pytest fixtures for the test suite."""

# stdlib
import asyncio
from typing import AsyncGenerator

# third-party
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# local
from src.models.base import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Use a single event loop for the whole test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    """Create an in-memory SQLite engine and apply all migrations."""
    _engine = create_async_engine(TEST_DB_URL, echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    await _engine.dispose()


@pytest.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional session that is rolled back after each test."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess
        await sess.rollback()
