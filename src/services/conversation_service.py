"""ConversationService — orchestrates conversation context and LLM responses."""

# stdlib
import logging

# local
from src.config import settings
from src.repositories.conversation_repo import ConversationRepository
from src.services.llm_service import LLMService, LLMServiceError

logger = logging.getLogger(__name__)


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

        await self._repo.add_message(
            conversation_id=conversation.id,
            role="user",
            content=user_message,
        )

        context = await self._repo.get_recent_messages(
            conversation_id=conversation.id,
            limit=settings.max_context_messages,
        )

        try:
            ai_response = await self._llm.complete(messages=context)
        except LLMServiceError:
            logger.exception("LLM request failed for user_id=%s", user_id)
            return "Произошла ошибка при обращении к AI. Попробуй позже."

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
