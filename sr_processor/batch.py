"""Batch orchestration for processing multiple PDFs."""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from tqdm import tqdm

from sr_processor.api import AnthropicCoder
from sr_processor.config import ProcessorConfig
from sr_processor.csv_export import assemble_csv
from sr_processor.exceptions import ProcessingCancelled
from sr_processor.logging_setup import setup_logging
from sr_processor.paper import PaperResult, PaperStatus, process_single_pdf, should_process
from sr_processor.prompt import load_prompt_from_docx
from sr_processor.rate_limiter import ApiRateLimiter


@dataclass
class BatchResult:
    total: int = 0
    successful: int = 0
    parse_errors: int = 0
    failed: int = 0
    skipped: int = 0
    cancelled: bool = False
    results: list[PaperResult] = field(default_factory=list)
    csv_path: Path | None = None

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "successful": self.successful,
            "parse_errors": self.parse_errors,
            "failed": self.failed,
            "skipped": self.skipped,
            "cancelled": self.cancelled,
            "csv_path": str(self.csv_path) if self.csv_path else None,
            "papers": [
                {
                    "name": r.pdf_name,
                    "status": r.status.value,
                    "message": r.message,
                    "eligible": r.eligible,
                    "confidence": r.confidence,
                }
                for r in self.results
            ],
        }


def discover_pdfs(pdf_folder: Path, max_pdfs: int | None = None) -> list[Path]:
    files = sorted(pdf_folder.glob("*.pdf"))
    if max_pdfs is not None:
        files = files[:max_pdfs]
    return files


def run_batch(
    config: ProcessorConfig,
    api_key: str | None = None,
    assemble: bool = True,
    on_progress: callable | None = None,
    should_cancel: callable | None = None,
) -> BatchResult:
    """
    Process all PDFs in pdf_folder; write JSON to output_folder.
    Skips successful papers; retries failures and parse errors.
    """
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    config.output_folder.mkdir(parents=True, exist_ok=True)
    logger = setup_logging(config.log_file)

    logger.info("=" * 70)
    logger.info("SYSTEMATIC REVIEW — BATCH RUN")
    logger.info("PDF folder: %s", config.pdf_folder)
    logger.info("Output: %s | Workers: %s", config.output_folder, config.max_workers)
    logger.info("=" * 70)

    system_prompt = load_prompt_from_docx(config.prompt_file)
    logger.info("Prompt loaded (%d chars)", len(system_prompt))

    pdf_files = discover_pdfs(config.pdf_folder, config.max_pdfs)
    if not pdf_files:
        raise FileNotFoundError(f"No PDFs in {config.pdf_folder}")

    to_process = [p for p in pdf_files if should_process(config.output_folder, p.stem)]
    logger.info("Found %d PDF(s); %d to process", len(pdf_files), len(to_process))

    limiter = ApiRateLimiter(config.api_min_interval_sec)
    coder = AnthropicCoder(api_key, config, logger, limiter)

    batch_result = BatchResult(total=len(pdf_files))

    def _work(pdf_path: Path) -> PaperResult:
        return process_single_pdf(
            pdf_path,
            coder,
            config.output_folder,
            system_prompt,
            config,
            logger,
            should_cancel,
        )

    def _record(result: PaperResult) -> None:
        batch_result.results.append(result)
        if result.status == PaperStatus.SUCCESS:
            batch_result.successful += 1
        elif result.status == PaperStatus.PARSE_ERROR:
            batch_result.parse_errors += 1
        elif result.status == PaperStatus.FAILED:
            batch_result.failed += 1
        elif result.status == PaperStatus.SKIPPED:
            batch_result.skipped += 1
        if on_progress:
            on_progress(batch_result)

    cancelled = False

    # Sequential when cancellable (web UI stop) — avoids queueing all PDFs at once
    if should_cancel:
        with tqdm(total=len(pdf_files), desc="Processing") as bar:
            for pdf_path in pdf_files:
                if should_cancel():
                    cancelled = True
                    logger.info("Stop requested — halting batch")
                    break
                try:
                    _record(_work(pdf_path))
                except ProcessingCancelled:
                    cancelled = True
                    logger.info("Stop requested — halted mid-paper")
                    break
                bar.update(1)
    else:
        with ThreadPoolExecutor(max_workers=config.max_workers) as pool:
            futures = {pool.submit(_work, p): p for p in pdf_files}
            with tqdm(total=len(pdf_files), desc="Processing") as bar:
                for fut in as_completed(futures):
                    result = fut.result()
                    _record(result)
                    bar.update(1)

    if cancelled:
        logger.info("Batch cancelled by user")
        batch_result.cancelled = True

    logger.info(
        "Done — success: %d | parse errors: %d | failed: %d | skipped: %d",
        batch_result.successful,
        batch_result.parse_errors,
        batch_result.failed,
        batch_result.skipped,
    )

    meta = {
        "summary": batch_result.to_dict(),
        "config": {
            "model": config.model,
            "workers": config.max_workers,
            "pdf_folder": str(config.pdf_folder),
        },
    }
    (config.output_folder / "batch_summary.json").write_text(
        json.dumps(meta, indent=2)
    )

    if assemble:
        batch_result.csv_path = assemble_csv(config, logger)

    return batch_result
