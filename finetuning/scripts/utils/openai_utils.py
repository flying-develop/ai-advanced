"""OpenAI API utilities with exponential backoff retry."""

import logging
import re
import time

from openai import OpenAI, RateLimitError, APIError

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def strip_json_fences(text: str) -> str:
    """Strip markdown code fences from model output before JSON parsing.

    gpt-4o sometimes wraps JSON in ```json ... ``` despite instructions.
    """
    text = text.strip()
    m = _FENCE_RE.match(text)
    return m.group(1).strip() if m else text


def call_with_retry(
    client: OpenAI,
    messages: list[dict],
    model: str = "gpt-4o-mini",
    temperature: float = 0,
    max_tokens: int = 512,
    max_retries: int = 3,
) -> str:
    """OpenAI chat completion with exponential backoff."""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except RateLimitError:
            wait = 2 ** attempt * 5
            logger.warning("Rate limit hit, waiting %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
            time.sleep(wait)
        except APIError as e:
            wait = 2 ** attempt * 2
            logger.warning("API error: %s, waiting %ds (attempt %d/%d)", e, wait, attempt + 1, max_retries)
            if attempt == max_retries - 1:
                raise
            time.sleep(wait)
    raise RuntimeError("Max retries exceeded")


def call_with_retry_verbose(
    client: OpenAI,
    messages: list[dict],
    model: str = "gpt-4o-mini",
    temperature: float = 0,
    max_tokens: int = 512,
    max_retries: int = 3,
) -> tuple[str, int]:
    """OpenAI chat completion with exponential backoff. Returns (content, total_tokens)."""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""
            tokens = response.usage.total_tokens if response.usage else 0
            return content, tokens
        except RateLimitError:
            wait = 2 ** attempt * 5
            logger.warning("Rate limit hit, waiting %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
            time.sleep(wait)
        except APIError as e:
            wait = 2 ** attempt * 2
            logger.warning("API error: %s, waiting %ds (attempt %d/%d)", e, wait, attempt + 1, max_retries)
            if attempt == max_retries - 1:
                raise
            time.sleep(wait)
    raise RuntimeError("Max retries exceeded")
