"""Parse Claude Messages API content into the model's text reply.

Sonnet 5.5 (and other thinking models) often lead with a ThinkingBlock.
Those objects have no ``.text`` — ``content[0].text`` raises AttributeError.
Only ``type == "text"`` blocks are the coded JSON we persist.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = _FENCE_RE.sub("", text).strip()
    return text


def _block_type(block: Any) -> str | None:
    if isinstance(block, dict):
        raw = block.get("type")
    else:
        raw = getattr(block, "type", None)
    return str(raw) if raw is not None else None


def _block_text(block: Any) -> str | None:
    if isinstance(block, dict):
        text = block.get("text")
    else:
        text = getattr(block, "text", None)
    return text if isinstance(text, str) else None


def extract_response_text(content: Any) -> str:
    """Join text blocks from a Messages API ``response.content`` list."""
    if not content:
        raise ValueError("Claude returned an empty response (no content blocks)")

    parts: list[str] = []
    seen_types: list[str] = []
    for block in content:
        btype = _block_type(block)
        seen_types.append(btype or type(block).__name__)
        if btype is not None and btype != "text":
            continue
        text = _block_text(block)
        if text and text.strip():
            parts.append(text)

    if not parts:
        raise ValueError(
            "Claude returned no text to parse (content types: "
            + ", ".join(seen_types)
            + "). Thinking may have used the full max_tokens budget."
        )
    return "\n".join(parts).strip()


def parse_model_json(raw_text: str, logger: logging.Logger) -> dict[str, Any]:
    raw_text = strip_json_fences(raw_text)
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.warning("JSON parse error: %s", e)
        return {
            "parse_error": True,
            "raw_response": raw_text,
            "eligible": None,
        }
