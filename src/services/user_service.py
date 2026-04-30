"""UserService — business logic for user management."""

# stdlib
import hashlib
import logging

# local
from src.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


class UserService:
    """Manages user-level operations such as auth token storage."""

    def __init__(self, user_repo: UserRepository) -> None:
        self._repo = user_repo

    async def save_auth_token(self, user_id: int, token: str) -> None:
        """Hash token with SHA-256 and persist it for user_id.

        The raw token is never written to the database — only its SHA-256
        hex digest is stored, preventing secret exposure if the DB is leaked.

        Args:
            user_id: Telegram user ID.
            token: Plain-text auth token received from the user.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        await self._repo.save_auth_token(user_id=user_id, token_hash=token_hash)
        logger.info("Auth token saved for user_id=%s", user_id)
