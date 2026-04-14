"""LLMService — async wrapper around the Anthropic SDK."""

# stdlib
import logging
from typing import Optional

# third-party
import anthropic

# local
from src.config import settings
from src.models.conversation import Message

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Raised when a call to the LLM API fails."""

    pass


class LLMService:
    """Manages communication with the Anthropic Claude API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or settings.anthropic_api_key
        )
        self._model = model or settings.llm_model

    async def complete(self, messages: list[Message]) -> str:
        """Send a list of conversation messages to the LLM and return the reply.

        Args:
            messages: Ordered list of Message ORM objects (oldest first).

        Returns:
            The assistant's text response.

        Raises:
            LLMServiceError: If the API call fails for any reason.
        """
        formatted = self._format_messages(messages)
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                messages=formatted,
            )
            return response.content[0].text
        except anthropic.APIError as exc:
            logger.exception("Anthropic API error: %s", exc)
            raise LLMServiceError(f"Anthropic API error: {exc}") from exc
        except Exception as exc:
            logger.exception("Unexpected error calling LLM: %s", exc)
            raise LLMServiceError(f"Unexpected LLM error: {exc}") from exc

    def _format_messages(
        self, messages: list[Message]
    ) -> list[dict[str, str]]:
        """Convert ORM Message objects to Anthropic API message dicts."""
        return [{"role": msg.role, "content": msg.content} for msg in messages]
