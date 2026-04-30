"""SQLAlchemy ORM model for the User entity."""

# stdlib
import logging

# third-party
from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

# local
from src.models.base import Base, TimestampMixin

logger = logging.getLogger(__name__)


class User(TimestampMixin, Base):
    """Represents the bot's single authenticated user."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    # SHA-256 hex digest (64 chars) — raw token is never persisted
    auth_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return f"<User id={self.id} user_id={self.user_id}>"
