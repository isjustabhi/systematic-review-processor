"""Configuration for batch processing."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProcessorConfig:
    pdf_folder: Path
    output_folder: Path
    prompt_file: Path

    model: str = "claude-sonnet-4-6"
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
