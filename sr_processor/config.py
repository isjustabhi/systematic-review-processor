"""Configuration for batch processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "claude-sonnet-5-5"

# Web UI choices. CLI --model may pass any Anthropic id.
SUPPORTED_MODELS: tuple[tuple[str, str], ...] = (
    ("claude-sonnet-5-5", "Claude Sonnet 5.5 (recommended)"),
    ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
)

# Sonnet 5.5 turns thinking on by default. `thinking: disabled` is a 400;
# `between_tools` is the supported off-switch. Without tools the reply is
# text-only, which keeps JSON coding cheap and avoids burning max_tokens
# on reasoning. Parser still accepts thinking blocks if they appear.
_BETWEEN_TOOLS_PREFIXES: tuple[str, ...] = (
    "claude-sonnet-5-5",
    "claude-sonnet-5.5",
)


def supported_model_ids() -> tuple[str, ...]:
    return tuple(model_id for model_id, _label in SUPPORTED_MODELS)


def resolve_ui_model(model: str | None) -> str:
    """Validate a web-UI model choice. Empty → default."""
    chosen = (model or DEFAULT_MODEL).strip()
    allowed = set(supported_model_ids())
    if chosen not in allowed:
        raise ValueError(
            f"Unsupported model {chosen!r}. Choose one of: {', '.join(supported_model_ids())}"
        )
    return chosen


def api_create_kwargs(model: str) -> dict[str, Any]:
    """Extra Messages API fields that depend on the selected model."""
    extra: dict[str, Any] = {}
    lowered = (model or "").lower()
    if any(lowered == p or lowered.startswith(p + "-") for p in _BETWEEN_TOOLS_PREFIXES):
        extra["thinking"] = {"type": "between_tools"}
    return extra


@dataclass
class ProcessorConfig:
    pdf_folder: Path
    output_folder: Path
    prompt_file: Path

    model: str = DEFAULT_MODEL
    max_tokens: int = 4096
    max_workers: int = 1
    max_pdfs: int | None = None

    max_retries: int = 6
    initial_delay: float = 2.0
    max_retry_delay: float = 60.0
    api_min_interval_sec: float = 4.0

    list_fields: tuple[str, ...] = field(
        default_factory=lambda: (
            "health_behavior",
            "health_biomarker",
            "clinical_endpoint",
        )
    )

    @property
    def log_file(self) -> Path:
        return self.output_folder / "processor.log"

    @property
    def csv_path(self) -> Path:
        return self.output_folder / "systematic_review_results.csv"
