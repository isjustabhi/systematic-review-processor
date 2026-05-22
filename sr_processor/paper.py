"""Single-paper processing and output status."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from sr_processor.api import AnthropicCoder
from sr_processor.config import ProcessorConfig
from sr_processor.pdf import extract_pdf_text


class PaperStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    PARSE_ERROR = "parse_error"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PaperResult:
    pdf_name: str
    status: PaperStatus
    message: str = ""
    eligible: Any = None
    confidence: Any = None
    input_tokens: int = 0
    output_tokens: int = 0


def _output_path(output_folder: Path, pdf_name: str) -> Path:
    return output_folder / f"{pdf_name}.json"


def _error_path(output_folder: Path, pdf_name: str) -> Path:
    return output_folder / f"{pdf_name}_ERROR.json"


def get_paper_status(output_folder: Path, pdf_name: str) -> PaperStatus:
    out = _output_path(output_folder, pdf_name)
    if not out.exists():
        return PaperStatus.PENDING

    try:
        data = json.loads(out.read_text())
    except json.JSONDecodeError:
        return PaperStatus.PENDING

    if data.get("parse_error"):
        return PaperStatus.PARSE_ERROR
    return PaperStatus.SUCCESS


def should_process(output_folder: Path, pdf_name: str, retry_errors: bool = True) -> bool:
    status = get_paper_status(output_folder, pdf_name)
    if status == PaperStatus.SUCCESS:
        return False
    if status == PaperStatus.PARSE_ERROR:
        return True
    if retry_errors and _error_path(output_folder, pdf_name).exists():
        return True
    return status == PaperStatus.PENDING


def process_single_pdf(
    pdf_path: Path,
    coder: AnthropicCoder,
    output_folder: Path,
    system_prompt: str,
    config: ProcessorConfig,
    logger: logging.Logger,
) -> PaperResult:
    pdf_name = pdf_path.stem
    output_path = _output_path(output_folder, pdf_name)
    error_path = _error_path(output_folder, pdf_name)

    if not should_process(output_folder, pdf_name):
        logger.info("Skipping %s (already coded)", pdf_name)
        return PaperResult(pdf_name, PaperStatus.SKIPPED, "Already processed")

    if error_path.exists():
        error_path.unlink()

    if output_path.exists() and get_paper_status(output_folder, pdf_name) == PaperStatus.PARSE_ERROR:
        output_path.unlink()

    try:
        pdf_text = extract_pdf_text(pdf_path)
        result, usage = coder.code_paper(pdf_text, system_prompt)

        result["_source_file"] = pdf_path.name
        result["_model"] = config.model
        result["_processed_timestamp"] = datetime.now(timezone.utc).isoformat()

        output_path.write_text(json.dumps(result, indent=2))

        if result.get("parse_error"):
            logger.warning("⚠ %s | JSON parse issue — saved for review", pdf_name)
            return PaperResult(
                pdf_name,
                PaperStatus.PARSE_ERROR,
                "Model response was not valid JSON",
                result.get("eligible"),
                result.get("confidence"),
                getattr(usage, "input_tokens", 0),
                usage.output_tokens,
            )

        logger.info(
            "✓ %s | Eligible: %s | Confidence: %s | in=%s out=%s",
            pdf_name,
            result.get("eligible"),
            result.get("confidence"),
            getattr(usage, "input_tokens", 0),
            usage.output_tokens,
        )
        return PaperResult(
            pdf_name,
            PaperStatus.SUCCESS,
            "",
            result.get("eligible"),
            result.get("confidence"),
            getattr(usage, "input_tokens", 0),
            usage.output_tokens,
        )

    except Exception as e:
        msg = str(e)
        logger.error("✗ %s: %s", pdf_name, msg)
        error_path.write_text(
            json.dumps(
                {
                    "error": msg,
                    "source_file": pdf_path.name,
                    "_processed_timestamp": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            )
        )
        return PaperResult(pdf_name, PaperStatus.FAILED, msg)
