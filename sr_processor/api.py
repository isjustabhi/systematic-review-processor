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

    def code_paper(self, pdf_text: str, system_prompt: str) -> tuple[dict[str, Any], Any]:
        user_message = build_user_message(pdf_text)

        delay = self._config.initial_delay
        last_error: Exception | None = None

        for attempt in range(self._config.max_retries):
            try:
                self._limiter.acquire()
                create_kwargs: dict[str, Any] = {
                    "model": self._config.model,
                    "max_tokens": self._config.max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_message}],
                }
                create_kwargs.update(api_create_kwargs(self._config.model))
                try:
                    response = self._client.messages.create(**create_kwargs)
                except TypeError:
                    # Older anthropic SDKs reject the thinking= kwarg.
                    create_kwargs.pop("thinking", None)
                    response = self._client.messages.create(**create_kwargs)
                raw = extract_response_text(response.content)
                return parse_model_json(raw, self._logger), response.usage

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
