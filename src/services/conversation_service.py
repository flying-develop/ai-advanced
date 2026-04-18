"""ConversationService — orchestrates conversation context and LLM responses."""

# stdlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# local
from src.config import settings
from src.repositories.conversation_repo import ConversationRepository
from src.services.llm_service import LLMService, LLMServiceError
from src.utils.messages import LLM_ERROR_FALLBACK

logger = logging.getLogger(__name__)


@dataclass
class UserStats:
    """Aggregated statistics for a single user."""

    conversation_count: int
    message_count: int
    first_message_at: Optional[datetime]


class ConversationNotFoundError(Exception):
    """Raised when an expected conversation does not exist."""

    pass


class ConversationService:
    """Business logic for managing AI conversations."""

    def __init__(
        self,
        llm_service: LLMService,
        conversation_repo: ConversationRepository,
    ) -> None:
        self._llm = llm_service
        self._repo = conversation_repo

    async def get_ai_response(self, user_id: int, user_message: str) -> str:
        """Process user message: save, build context, call LLM, save response.

        Args:
            user_id: Telegram user ID.
            user_message: The text sent by the user.

        Returns:
            AI-generated response text.
        """
        conversation = await self._repo.get_or_create(user_id=user_id)

        # Build context from existing messages before adding the new user message,
        # so that on LLM failure nothing is persisted (atomic save below).
        existing_context = await self._repo.get_recent_messages(
            conversation_id=conversation.id,
            limit=settings.max_context_messages - 1,
        )

        # Append the incoming user message to context for LLM without persisting yet.
        from src.models.conversation import Message as MessageModel  # local import to avoid circular

        pending_user_msg = MessageModel(
            conversation_id=conversation.id,
            role="user",
            content=user_message,
        )
        context = existing_context + [pending_user_msg]

        try:
            t0 = time.monotonic()
            ai_response = await self._llm.complete(messages=context)
            elapsed = time.monotonic() - t0
            logger.info("LLM response in %.2fs for user_id=%s", elapsed, user_id)
        except LLMServiceError:
            logger.exception("LLM request failed for user_id=%s", user_id)
            return LLM_ERROR_FALLBACK

        # Persist both messages only after a successful LLM response.
        await self._repo.add_message(
            conversation_id=conversation.id,
            role="user",
            content=user_message,
        )
        await self._repo.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content=ai_response,
        )

        logger.info(
            "AI response generated for user_id=%s, conv_id=%s",
            user_id,
            conversation.id,
        )
        return ai_response

    async def reset_conversation(self, user_id: int) -> None:
        """Deactivate current conversation so the next message starts fresh.

        Args:
            user_id: Telegram user ID.
        """
        conversation = await self._repo.get_active(user_id=user_id)
        if conversation:
            await self._repo.deactivate(conversation)
            logger.info("Conversation reset for user_id=%s", user_id)

    async def start_new_conversation(self, user_id: int) -> bool:
        """Deactivate current conversation (if any) and create a new one.

        Args:
            user_id: Telegram user ID.

        Returns:
            True if a previous active conversation was deactivated, False otherwise.
        """
        existing = await self._repo.get_active(user_id=user_id)
        had_previous = existing is not None
        if existing:
            await self._repo.deactivate(existing)
            logger.info("Conversation deactivated for user_id=%s", user_id)

        new_conversation = await self._repo.get_or_create(user_id=user_id)
        logger.info(
            "New conversation started for user_id=%s, conv_id=%s",
            user_id,
            new_conversation.id,
        )
        return had_previous

    async def get_stats(self, user_id: int) -> UserStats:
        """Collect aggregated statistics for the given user.

        Args:
            user_id: Telegram user ID.

        Returns:
            UserStats with conversation_count, message_count, and first_message_at.
        """
        conversation_count = await self._repo.count_conversations(user_id=user_id)
        message_count = await self._repo.count_messages(user_id=user_id)
        first_message_at = await self._repo.get_first_message_date(user_id=user_id)
        return UserStats(
            conversation_count=conversation_count,
            message_count=message_count,
            first_message_at=first_message_at,
        )
