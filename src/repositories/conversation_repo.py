"""ConversationRepository — data access layer for Conversation and Message entities."""

# stdlib
import logging
from typing import Optional

# third-party
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# local
from src.models.conversation import Conversation, Message
from src.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ConversationRepository(BaseRepository[Conversation]):
    """Repository for managing conversations and their messages."""

    model = Conversation

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_or_create(self, user_id: int) -> Conversation:
        """Get the active conversation for user_id, or create a new one."""
        stmt = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        conversation = result.scalar_one_or_none()

        if conversation is None:
            conversation = Conversation(user_id=user_id)
            self._session.add(conversation)
            await self._session.flush()
            logger.info("Created new conversation for user_id=%s", user_id)

        return conversation

    async def get_active(self, user_id: int) -> Optional[Conversation]:
        """Return active conversation for user_id, or None if not found."""
        stmt = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def deactivate(self, conversation: Conversation) -> None:
        """Mark a conversation as inactive (soft-close)."""
        conversation.is_active = False
        await self._session.flush()

    async def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
    ) -> Message:
        """Append a message to the given conversation."""
        message = Message(conversation_id=conversation_id, role=role, content=content)
        self._session.add(message)
        await self._session.flush()
        return message

    async def get_recent_messages(
        self,
        conversation_id: int,
        limit: int = 20,
    ) -> list[Message]:
        """Return the most recent `limit` messages ordered oldest-first."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        messages = list(result.scalars().all())
        # Return in chronological order (oldest first) for LLM context
        return list(reversed(messages))
