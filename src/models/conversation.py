"""SQLAlchemy ORM models for Conversation and Message entities."""

# stdlib
import logging

# third-party
from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

# local
from src.models.base import Base, TimestampMixin

logger = logging.getLogger(__name__)


class Conversation(TimestampMixin, Base):
    """Represents a single ongoing conversation with a user."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        order_by="Message.id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} user_id={self.user_id} active={self.is_active}>"


class Message(TimestampMixin, Base):
    """Represents a single message within a conversation."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} role={self.role} conv={self.conversation_id}>"
