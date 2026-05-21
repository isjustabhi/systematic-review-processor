"""Anthropic API client with retries and rate limiting."""

import json
import logging
import re
import time
from typing import Any, Callable

import anthropic

from sr_processor.config import ProcessorConfig
from sr_processor.exceptions import ProcessingCancelled
from sr_processor.rate_limiter import ApiRateLimiter

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = _FENCE_RE.sub("", text).strip()
    return text


def _parse_model_json(raw_text: str, logger: logging.Logger) -> dict[str, Any]:
    raw_text = _strip_json_fences(raw_text)
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.warning("JSON parse error: %s", e)
        return {
            "parse_error": True,
            "raw_response": raw_text,
            "eligible": None,
        }


def _check_cancel(should_cancel: Callable[[], bool] | None) -> None:
    if should_cancel and should_cancel():
        raise ProcessingCancelled()


def _interruptible_sleep(seconds: float, should_cancel: Callable[[], bool] | None) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        _check_cancel(should_cancel)
        time.sleep(min(0.4, end - time.monotonic()))


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

    def code_paper(
        self,
        pdf_text: str,
        system_prompt: str,
        should_cancel: Callable[[], bool] | None = None,
    ) -> tuple[dict[str, Any], Any]:
        user_message = (
            "Code this paper per the systematic review instructions. "
            "Return ONLY a valid JSON object with no markdown or commentary.\n\n"
            + pdf_text
        )

        delay = self._config.initial_delay
        last_error: Exception | None = None

        for attempt in range(self._config.max_retries):
            _check_cancel(should_cancel)
            try:
                self._limiter.acquire()
                _check_cancel(should_cancel)
                response = self._client.messages.create(
                    model=self._config.model,
                    max_tokens=self._config.max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )
                raw = response.content[0].text.strip()
                return _parse_model_json(raw, self._logger), response.usage

            except ProcessingCancelled:
                raise
            except anthropic.RateLimitError as e:
                last_error = e
                if attempt >= self._config.max_retries - 1:
                    raise
                wait = min(delay, self._config.max_retry_delay)
                self._logger.warning(
                    "Rate limited. Waiting %.1fs (attempt %d)...", wait, attempt + 1
                )
                _interruptible_sleep(wait, should_cancel)
                delay *= 2

            except anthropic.APIError as e:
                self._logger.error("API error: %s", e)
                raise

        raise RuntimeError("Max retries exceeded.") from last_error
