"""Async OpenAI API client wrapper — same interface as AnthropicClient."""

import logging

import openai

from gateway.src.proxy.llm_client import LLMClientError, LLMResponse

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Thin async wrapper around the OpenAI SDK, returning the shared LLMResponse."""

    def __init__(self, api_key: str) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def complete(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 1024,
        system: str | None = None,
    ) -> LLMResponse:
        """Send a chat completion request and return a structured response."""
        # OpenAI places the system prompt as the first message with role="system".
        full_messages: list[dict] = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=full_messages,  # type: ignore[arg-type]
                max_tokens=max_tokens,
            )
        except openai.APIStatusError as exc:
            raise LLMClientError(
                f"OpenAI API error: {exc.message}", status_code=exc.status_code
            ) from exc

        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            model=response.model,
            stop_reason=choice.finish_reason or "unknown",
        )
