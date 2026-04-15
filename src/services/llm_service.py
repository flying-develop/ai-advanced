"""LLMService — async wrapper around the Qwen (DashScope) OpenAI-compatible API."""

# stdlib
import logging
from typing import Optional

# third-party
import httpx

# local
from src.config import settings
from src.models.conversation import Message

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Raised when a call to the LLM API fails."""

    pass


class LLMService:
    """Manages communication with the Qwen API (OpenAI-compatible format)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or settings.qwen_api_key
        self._model = model or settings.llm_model
        self._base_url = (base_url or settings.qwen_base_url).rstrip("/")

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
        payload = {
            "model": self._model,
            "messages": formatted,
            "max_tokens": 2048,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            logger.exception("Qwen API HTTP error %s: %s", exc.response.status_code, exc)
            raise LLMServiceError(f"Qwen API HTTP error {exc.response.status_code}") from exc
        except Exception as exc:
            logger.exception("Unexpected error calling LLM: %s", exc)
            raise LLMServiceError(f"Unexpected LLM error: {exc}") from exc

    def _format_messages(
        self, messages: list[Message]
    ) -> list[dict[str, str]]:
        """Convert ORM Message objects to OpenAI-compatible message dicts."""
        return [{"role": msg.role, "content": msg.content} for msg in messages]
