"""Background batch job for the web UI."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from sr_processor.batch import run_batch
from sr_processor.config import DEFAULT_MODEL, ProcessorConfig, resolve_ui_model

from api.workspace import MAX_PAPERS, Workspace


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
    _session_api_key: str | None = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    state: JobState = JobState.IDLE
    message: str = ""
    workers: int = 1
    model: str = DEFAULT_MODEL
    progress: dict = field(default_factory=dict)
    _listeners: list[Callable[[dict], None]] = field(default_factory=list, repr=False)

    def api_key_info(self) -> dict:
        env = bool(os.getenv("ANTHROPIC_API_KEY"))
        session = bool(self._session_api_key)
        return {
            "api_key_set": env or session,
            "api_key_source": (
                "session" if session and not env else "env" if env else None
            ),
        }

    def set_api_key(self, key: str) -> None:
        key = key.strip()
        if len(key) < 10:
            raise ValueError("API key looks too short")
        self._session_api_key = key

    def clear_api_key(self) -> None:
        self._session_api_key = None

    def _resolve_api_key(self) -> str:
        if os.getenv("ANTHROPIC_API_KEY"):
            return os.environ["ANTHROPIC_API_KEY"]
        if self._session_api_key:
            return self._session_api_key
        raise RuntimeError(
            "No API key — paste your Anthropic key in Step 1 or add ANTHROPIC_API_KEY to .env"
        )

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
        base.update(self.api_key_info())
        with self._lock:
            base["job"] = {
                "state": self.state.value,
                "message": self.message,
                "workers": self.workers,
                "model": self.model,
                "progress": self.progress,
            }
        return base

    def is_running(self) -> bool:
        return self.state in (JobState.RUNNING, JobState.STOPPING)

    def start(self, workers: int = 1, model: str | None = None) -> None:
        chosen = resolve_ui_model(model)
        with self._lock:
            if self.state == JobState.RUNNING:
                raise RuntimeError("A job is already running")
            self._resolve_api_key()
            if not self.workspace.prompt_path.is_file():
                raise RuntimeError("Upload your coding prompt (.docx) in Step 2")
            if not self.workspace.list_pdfs():
                raise RuntimeError("Upload at least one PDF in Step 3")

            self._cancel.clear()
            self.workers = 1
            self.model = chosen
            self.state = JobState.RUNNING
            self.message = "Processing papers…"
            self.progress = {}

        api_key = self._resolve_api_key()

        def _run() -> None:
            try:
                config = ProcessorConfig(
                    pdf_folder=self.workspace.papers_dir,
                    output_folder=self.workspace.output_dir,
                    prompt_file=self.workspace.prompt_path,
                    model=self.model,
                    max_workers=1,
                    max_pdfs=MAX_PAPERS,
                    api_min_interval_sec=5.0,
                )

                def on_progress(batch_result) -> None:
                    done = (
                        batch_result.successful
                        + batch_result.parse_errors
                        + batch_result.failed
                        + batch_result.skipped
                    )
                    with self._lock:
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
                    api_key=api_key,
                    assemble=True,
                    on_progress=on_progress,
                    should_cancel=self._cancel.is_set,
                )

                with self._lock:
                    if result.cancelled or self._cancel.is_set():
                        self.state = JobState.CANCELLED
                        self.message = "Stopped"
                    elif result.failed > 0:
                        self.state = JobState.COMPLETED
                        self.message = f"Finished — {result.failed} paper(s) failed (see list)"
                    else:
                        self.state = JobState.COMPLETED
                        self.message = "All papers coded — download your CSV"
            except Exception as e:
                with self._lock:
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
                self.message = "Stopping after current paper…"
        self._notify()
