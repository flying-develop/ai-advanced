"""UserRepository — data access layer for the User entity."""

# stdlib
import logging

# third-party
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# local
from src.models.user import User
from src.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User]):
    """Repository for managing user records."""

    model = User

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_or_create(self, user_id: int) -> User:
        """Return the User row for user_id, creating it if absent."""
        stmt = select(User).where(User.user_id == user_id)
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            user = User(user_id=user_id)
            self._session.add(user)
            await self._session.flush()
            logger.info("Created user record for user_id=%s", user_id)

        return user

    async def save_auth_token(self, user_id: int, token_hash: str) -> User:
        """Persist the pre-hashed token for user_id and return the updated User."""
        user = await self.get_or_create(user_id=user_id)
        user.auth_token_hash = token_hash
        await self._session.flush()
        logger.info("Auth token updated for user_id=%s", user_id)
        return user
