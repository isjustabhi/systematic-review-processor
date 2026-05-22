"""Filesystem-backed batch workspaces."""

import json
import shutil
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class BatchState(str, Enum):
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BatchStore:
    def __init__(self, root: Path, max_pdfs_per_batch: int = 20):
        self.root = root
        self.max_pdfs = max_pdfs_per_batch
        self.root.mkdir(parents=True, exist_ok=True)

    def _batch_dir(self, batch_id: str) -> Path:
        return self.root / batch_id

    def create(self) -> str:
        batch_id = uuid.uuid4().hex[:12]
        d = self._batch_dir(batch_id)
        (d / "pdfs").mkdir(parents=True)
        (d / "output").mkdir(parents=True)
        self._write_meta(
            batch_id,
            {
                "batch_id": batch_id,
                "state": BatchState.CREATED.value,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "pdf_count": 0,
            },
        )
        return batch_id

    def _meta_path(self, batch_id: str) -> Path:
        return self._batch_dir(batch_id) / "meta.json"

    def _write_meta(self, batch_id: str, data: dict) -> None:
        self._meta_path(batch_id).write_text(json.dumps(data, indent=2))

    def read_meta(self, batch_id: str) -> dict:
        path = self._meta_path(batch_id)
        if not path.exists():
            raise FileNotFoundError(f"Batch not found: {batch_id}")
        return json.loads(path.read_text())

    def update_meta(self, batch_id: str, **kwargs) -> dict:
        meta = self.read_meta(batch_id)
        meta.update(kwargs)
        self._write_meta(batch_id, meta)
        return meta

    def pdfs_dir(self, batch_id: str) -> Path:
        return self._batch_dir(batch_id) / "pdfs"

    def output_dir(self, batch_id: str) -> Path:
        return self._batch_dir(batch_id) / "output"

    def prompt_path(self, batch_id: str) -> Path:
        return self._batch_dir(batch_id) / "prompt.docx"

    def save_prompt(self, batch_id: str, content: bytes) -> None:
        self.prompt_path(batch_id).write_bytes(content)
        self.update_meta(batch_id, state=BatchState.READY.value)

    def add_pdfs(self, batch_id: str, files: list[tuple[str, bytes]]) -> int:
        dest = self.pdfs_dir(batch_id)
        existing = list(dest.glob("*.pdf"))
        if len(existing) + len(files) > self.max_pdfs:
            raise ValueError(f"Maximum {self.max_pdfs} PDFs per batch")

        for name, data in files:
            if not name.lower().endswith(".pdf"):
                continue
            (dest / Path(name).name).write_bytes(data)

        count = len(list(dest.glob("*.pdf")))
        self.update_meta(batch_id, pdf_count=count, state=BatchState.READY.value)
        return count

    def list_pdf_paths(self, batch_id: str) -> list[Path]:
        return sorted(self.pdfs_dir(batch_id).glob("*.pdf"))

    def exists(self, batch_id: str) -> bool:
        return self._meta_path(batch_id).exists()
