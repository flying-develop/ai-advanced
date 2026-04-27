"""ConversationService — orchestrates conversation context and LLM responses."""

# stdlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# local
from src.config import settings
from src.models.conversation import Message as MessageModel
from src.repositories.conversation_repo import ConversationRepository
from src.services.injection_guard import InjectionGuard
from src.services.llm_service import LLMService, LLMServiceError
from src.utils.messages import INJECTION_BLOCKED_MESSAGE, INJECTION_OUTPUT_BLOCKED, LLM_ERROR_FALLBACK

logger = logging.getLogger(__name__)
attack_logger = logging.getLogger("attack_log")


def _log_attack(
    *,
    stage: str,
    attack_type: str | None,
    user_input: str,
    result: str,
    response: str,
    protection: bool,
) -> None:
    """Emit a structured attack-log entry that mirrors the day11-attack-log.md format."""
    attack_logger.warning(
        "\n"
        "┌─ ATTACK LOG ──────────────────────────────────────\n"
        "│ Stage      : %s\n"
        "│ Type       : %s\n"
        "│ Protection : %s\n"
        "│ Input      : %.120s\n"
        "│ Result     : %s\n"
        "│ Response   : %.120s\n"
        "└────────────────────────────────────────────────────",
        stage,
        attack_type or "unknown",
        "ENABLED" if protection else "DISABLED",
        user_input.replace("\n", " "),
        result,
        response.replace("\n", " "),
    )


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
        injection_guard: InjectionGuard | None = None,
    ) -> None:
        self._llm = llm_service
        self._repo = conversation_repo
        self._guard = injection_guard

    async def get_ai_response(self, user_id: int, user_message: str) -> str:
        """Process user message: save, build context, call LLM, save response.

        Args:
            user_id: Telegram user ID.
            user_message: The text sent by the user.

        Returns:
            AI-generated response text, or a human-readable fallback on LLM error.

        Raises:
            Does not propagate LLMServiceError — it is caught and converted to a fallback string.
        """
        conversation = await self._repo.get_or_create(user_id=user_id)

        # Build context from existing messages before adding the new user message,
        # so that on LLM failure nothing is persisted (atomic save below).
        existing_context = await self._repo.get_recent_messages(
            conversation_id=conversation.id,
            limit=settings.max_context_messages - 1,
        )

        # Append the incoming user message to context for LLM without persisting yet.
        pending_user_msg = MessageModel(
            conversation_id=conversation.id,
            role="user",
            content=user_message,
        )
        context = existing_context + [pending_user_msg]

        input_check = self._guard.check_input(user_message) if self._guard is not None else None

        if input_check is not None and not input_check.is_safe:
            _log_attack(
                stage="INPUT",
                attack_type=input_check.attack_type,
                user_input=user_message,
                result="BLOCKED",
                response=INJECTION_BLOCKED_MESSAGE,
                protection=True,
            )
            return INJECTION_BLOCKED_MESSAGE

        try:
            t0 = time.monotonic()
            ai_response = await self._llm.complete(messages=context)
            elapsed = time.monotonic() - t0
            logger.info("LLM response in %.2fs for user_id=%s", elapsed, user_id)
        except LLMServiceError:
            logger.exception("LLM request failed for user_id=%s", user_id)
            return LLM_ERROR_FALLBACK

        if self._guard is not None:
            output_check = self._guard.check_output(ai_response)
            if not output_check.is_safe:
                _log_attack(
                    stage="OUTPUT",
                    attack_type=output_check.attack_type,
                    user_input=user_message,
                    result="BLOCKED",
                    response=INJECTION_OUTPUT_BLOCKED,
                    protection=True,
                )
                return INJECTION_OUTPUT_BLOCKED

            # Attack pattern was detected by input guard but slipped past hardened prompt.
            if input_check is not None and not input_check.is_safe:
                _log_attack(
                    stage="PASSED",
                    attack_type=input_check.attack_type,
                    user_input=user_message,
                    result="SUCCEEDED — hardened prompt did not hold",
                    response=ai_response,
                    protection=True,
                )

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

        Returns:
            None. No-op if no active conversation exists.
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

    async def get_history(self, user_id: int, limit: int = 5) -> list[dict[str, str]]:
        """Return the last `limit` messages from the active conversation.

        Args:
            user_id: Telegram user ID.
            limit: Number of recent messages to fetch.

        Returns:
            List of dicts with keys "role" and "content", oldest-first.
        """
        messages = await self._repo.get_last_messages_for_user(
            user_id=user_id, limit=limit
        )
        return [{"role": msg.role, "content": msg.content} for msg in messages]

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
