"""Anthropic API client with retries and rate limiting."""

from __future__ import annotations

import logging
import time
from typing import Any

import anthropic

from sr_processor.config import ProcessorConfig, api_create_kwargs
from sr_processor.rate_limiter import ApiRateLimiter
from sr_processor.response import extract_response_text, parse_model_json
from sr_processor.schema import build_user_message

DIGEST_SYSTEM = (
    "You are preparing a briefing for a research assistant who will code papers. "
    "Read the following academic paper in detail. Produce a compact, faithful briefing "
    "they can use as background: purpose of the paper, key definitions, dimensions or "
    "categories, coding rules or criteria, and distinctions the authors insist on. "
    "Do not invent. Do not add advice that is not in the paper. Use short headings and "
    "bullet points. This briefing will be prepended to a separate coding protocol."
)

_RAW_FRAMEWORK_CAP = 80_000


class AnthropicCoder:
    def __init__(
        self,
        api_key: str,
        config: ProcessorConfig,
        logger: logging.Logger,
        limiter: ApiRateLimiter | None = None,
    ):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._config = config
        self._logger = logger
        self._limiter = limiter or ApiRateLimiter(config.api_min_interval_sec)

    def _complete(self, system: str, user: str, max_tokens: int | None = None) -> tuple[str, Any]:
        delay = self._config.initial_delay
        last_error: Exception | None = None
        tokens = max_tokens if max_tokens is not None else self._config.max_tokens

        for attempt in range(self._config.max_retries):
            try:
                self._limiter.acquire()
                create_kwargs: dict[str, Any] = {
                    "model": self._config.model,
                    "max_tokens": tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                }
                create_kwargs.update(api_create_kwargs(self._config.model))
                try:
                    response = self._client.messages.create(**create_kwargs)
                except TypeError:
                    # Older anthropic SDKs reject the thinking= kwarg.
                    create_kwargs.pop("thinking", None)
                    response = self._client.messages.create(**create_kwargs)
                raw = extract_response_text(response.content)
                return raw, response.usage

            except anthropic.RateLimitError as e:
                last_error = e
                if attempt >= self._config.max_retries - 1:
                    raise
                wait = min(delay, self._config.max_retry_delay)
                self._logger.warning("Rate limited. Waiting %.1fs (attempt %d)...", wait, attempt + 1)
                time.sleep(wait)
                delay *= 2

            except anthropic.APIError as e:
                self._logger.error("API error: %s", e)
                raise

        raise RuntimeError("Max retries exceeded.") from last_error

    def code_paper(self, pdf_text: str, system_prompt: str) -> tuple[dict[str, Any], Any]:
        raw, usage = self._complete(system_prompt, build_user_message(pdf_text))
        return parse_model_json(raw, self._logger), usage

    def digest_framework(self, pdf_text: str) -> str:
        """Step 1 of two-step prompting: read a framework PDF into a reusable briefing."""
        user = (
            "Read this paper in detail and write the briefing.\n\n"
            "--- PAPER TEXT ---\n\n"
            + pdf_text
        )
        raw, _usage = self._complete(DIGEST_SYSTEM, user)
        briefing = (raw or "").strip()
        if not briefing:
            raise ValueError("Framework briefing came back empty")
        return briefing


def fallback_framework_text(pdf_text: str) -> str:
    """If the digest call fails, still give the coder the extracted PDF text."""
    text = (pdf_text or "").strip()
    if len(text) > _RAW_FRAMEWORK_CAP:
        return text[:_RAW_FRAMEWORK_CAP] + "\n\n[truncated]"
    return text
