"""Background batch job for the web UI."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from sr_processor.batch import run_batch
from sr_processor.config import ProcessorConfig
from api.workspace import Workspace


class JobState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class JobRunner:
    workspace: Workspace
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    state: JobState = JobState.IDLE
    message: str = ""
    workers: int = 1
    progress: dict = field(default_factory=dict)
    _listeners: list[Callable[[dict], None]] = field(default_factory=list, repr=False)

    def subscribe(self, callback: Callable[[dict], None]) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        payload = self.get_status()
        for cb in list(self._listeners):
            try:
                cb(payload)
            except Exception:
                pass

    def get_status(self) -> dict:
        base = self.workspace.summary()
        with self._lock:
            base["job"] = {
                "state": self.state.value,
                "message": self.message,
                "workers": self.workers,
                "progress": self.progress,
            }
        return base

    def is_running(self) -> bool:
        return self.state in (JobState.RUNNING, JobState.STOPPING)

    def start(self, workers: int = 1) -> None:
        with self._lock:
            if self.is_running():
                raise RuntimeError("A job is already running")
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise RuntimeError("ANTHROPIC_API_KEY not set in .env")
            if not self.workspace.prompt_path.is_file():
                raise RuntimeError("Upload a coding prompt (.docx) first")
            if not self.workspace.list_pdfs():
                raise RuntimeError("Upload at least one PDF")

            self._cancel.clear()
            self.workers = 1  # always sequential for reliable stop
            self.state = JobState.RUNNING
            self.message = "Processing papers…"
            self.progress = {}

        def _run() -> None:
            try:
                config = ProcessorConfig(
                    pdf_folder=self.workspace.papers_dir,
                    output_folder=self.workspace.output_dir,
                    prompt_file=self.workspace.prompt_path,
                    max_workers=1,
                    max_pdfs=20,
                    api_min_interval_sec=4.0,
                )

                def on_progress(batch_result) -> None:
                    done = (
                        batch_result.successful
                        + batch_result.parse_errors
                        + batch_result.failed
                        + batch_result.skipped
                    )
                    with self._lock:
                        if self.state == JobState.STOPPING:
                            self.message = "Stopping…"
                        self.progress = {
                            "total": batch_result.total,
                            "done": done,
                            "successful": batch_result.successful,
                            "failed": batch_result.failed,
                            "parse_errors": batch_result.parse_errors,
                            "skipped": batch_result.skipped,
                            "current": (
                                batch_result.results[-1].pdf_name
                                if batch_result.results
                                else None
                            ),
                        }
                    self._notify()

                result = run_batch(
                    config,
                    assemble=True,
                    on_progress=on_progress,
                    should_cancel=self._cancel.is_set,
                )

                with self._lock:
                    if result.cancelled or self._cancel.is_set():
                        self.state = JobState.CANCELLED
                        self.message = "Stopped by user"
                    elif result.failed > 0:
                        self.state = JobState.COMPLETED
                        self.message = f"Done with {result.failed} failure(s)"
                    else:
                        self.state = JobState.COMPLETED
                        self.message = "All papers processed"
            except Exception as e:
                with self._lock:
                    if self._cancel.is_set():
                        self.state = JobState.CANCELLED
                        self.message = "Stopped by user"
                    else:
                        self.state = JobState.FAILED
                        self.message = str(e)
            finally:
                self._notify()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        self._notify()

    def stop(self) -> None:
        self._cancel.set()
        with self._lock:
            if self.state == JobState.RUNNING:
                self.state = JobState.STOPPING
                self.message = "Stopping now…"
        self._notify()

    def reset_idle(self) -> None:
        with self._lock:
            if not self.is_running():
                self.state = JobState.IDLE
                self.message = ""
