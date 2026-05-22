"""Workspace paths and per-paper status for the web UI."""

from __future__ import annotations

import json
from pathlib import Path

from sr_processor.paper import PaperStatus, get_paper_status

MAX_PAPERS = 20
PAPERS_DIR_NAME = "RAG Pilot Papers"
DEFAULT_PROMPT_NAME = "Claude_Code_Prompting_v4.docx"


class Workspace:
    def __init__(self, root: Path):
        self.root = root
        self.papers_dir = root / PAPERS_DIR_NAME
        self.output_dir = root / "output"
        self.prompt_path = root / DEFAULT_PROMPT_NAME

    def ensure_dirs(self) -> None:
        self.papers_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def list_pdfs(self) -> list[Path]:
        if not self.papers_dir.is_dir():
            return []
        return sorted(self.papers_dir.glob("*.pdf"))[:MAX_PAPERS]

    def paper_statuses(self) -> list[dict]:
        rows = []
        for pdf in self.list_pdfs():
            name = pdf.stem
            status = get_paper_status(self.output_dir, name)
            row = {
                "id": name,
                "filename": pdf.name,
                "status": status.value,
                "eligible": None,
                "confidence": None,
                "needs_human_review": None,
                "error": None,
            }
            out = self.output_dir / f"{name}.json"
            err = self.output_dir / f"{name}_ERROR.json"
            if out.exists():
                try:
                    data = json.loads(out.read_text())
                    row["eligible"] = data.get("eligible")
                    row["confidence"] = data.get("confidence")
                    row["needs_human_review"] = data.get("needs_human_review")
                    if data.get("parse_error"):
                        row["status"] = "parse_error"
                except json.JSONDecodeError:
                    pass
            if err.exists() and row["status"] == PaperStatus.PENDING.value:
                try:
                    row["status"] = "failed"
                    row["error"] = json.loads(err.read_text()).get("error", "")
                except json.JSONDecodeError:
                    pass
            rows.append(row)
        return rows

    def summary(self) -> dict:
        papers = self.paper_statuses()
        counts: dict[str, int] = {}
        for p in papers:
            counts[p["status"]] = counts.get(p["status"], 0) + 1
        csv = self.output_dir / "systematic_review_results.csv"
        return {
            "max_papers": MAX_PAPERS,
            "pdf_count": len(papers),
            "papers_folder": PAPERS_DIR_NAME,
            "prompt_ready": self.prompt_path.is_file(),
            "prompt_name": self.prompt_path.name if self.prompt_path.exists() else None,
            "csv_ready": csv.is_file(),
            "counts": counts,
            "papers": papers,
        }
