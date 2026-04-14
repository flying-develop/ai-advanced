"""BaseRepository — generic CRUD operations for SQLAlchemy models."""

# stdlib
import logging
from typing import Generic, Optional, TypeVar

# third-party
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# local
from src.models.base import Base

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic repository providing basic CRUD operations."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, entity_id: int) -> Optional[ModelT]:
        """Fetch a single entity by primary key."""
        return await self._session.get(self.model, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        """Persist a new entity and flush to obtain its PK."""
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        """Delete an entity from the session."""
        await self._session.delete(entity)
        await self._session.flush()

    async def list_all(self) -> list[ModelT]:
        """Return all rows for this model (use with caution on large tables)."""
        result = await self._session.execute(select(self.model))
        return list(result.scalars().all())
