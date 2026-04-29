"""Async Anthropic API client wrapper."""

import logging
from dataclasses import dataclass

import anthropic

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Raised when the upstream LLM API returns an error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class LLMResponse:
    """Structured response from the LLM."""

    content: str
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: str


class LLMClient:
    """Thin async wrapper around the Anthropic SDK."""

    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 1024,
        system: str | None = None,
    ) -> LLMResponse:
        """Send a chat completion request and return a structured response."""
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        try:
            response = await self._client.messages.create(**kwargs)
        except anthropic.APIStatusError as exc:
            raise LLMClientError(
                f"Anthropic API error: {exc.message}", status_code=exc.status_code
            ) from exc

        content_text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )
        return LLMResponse(
            content=content_text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
            stop_reason=response.stop_reason or "unknown",
        )
