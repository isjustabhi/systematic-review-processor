"""Systematic review PDF processing core."""

from sr_processor.batch import BatchResult, run_batch
from sr_processor.config import ProcessorConfig

__all__ = ["ProcessorConfig", "BatchResult", "run_batch"]
