"""Change log — papers that could not be coded cleanly.

Scans the output folder and produces a single human-readable report of every
paper that needs attention: hard failures (couldn't extract/code), JSON parse
errors, and papers the model flagged for human review. This is the list that is
useful for the final systematic-review write-up.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

CHANGE_LOG_CSV = "change_log.csv"
CHANGE_LOG_FIELDS = ["paper", "status", "reason", "timestamp"]


def _coalesce_timestamp(data: dict) -> str:
    return str(data.get("_processed_timestamp") or "")


def collect_change_log_rows(output_folder: Path) -> list[dict]:
    """Build change-log rows from the JSON / *_ERROR.json files on disk."""
    rows: list[dict] = []

    for err_path in sorted(output_folder.glob("*_ERROR.json")):
        paper = err_path.name[: -len("_ERROR.json")]
        try:
            data = json.loads(err_path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
        rows.append(
            {
                "paper": paper,
                "status": "failed",
                "reason": data.get("error", "Unknown error — could not code paper"),
                "timestamp": _coalesce_timestamp(data),
            }
        )

    for json_path in sorted(output_folder.glob("*.json")):
        name = json_path.name
        if name.endswith("_ERROR.json") or name in {
            "batch_summary.json",
        }:
            continue
        try:
            data = json.loads(json_path.read_text())
        except (json.JSONDecodeError, OSError):
            rows.append(
                {
                    "paper": json_path.stem,
                    "status": "parse_error",
                    "reason": "Output file was not valid JSON",
                    "timestamp": "",
                }
            )
            continue

        if data.get("parse_error"):
            rows.append(
                {
                    "paper": json_path.stem,
                    "status": "parse_error",
                    "reason": "Model response was not valid JSON — needs human review",
                    "timestamp": _coalesce_timestamp(data),
                }
            )
        elif data.get("needs_human_review"):
            rows.append(
                {
                    "paper": json_path.stem,
                    "status": "needs_review",
                    "reason": str(
                        data.get("human_review_reason")
                        or data.get("review_notes")
                        or "Model flagged this paper for human review"
                    ),
                    "timestamp": _coalesce_timestamp(data),
                }
            )

    rows.sort(key=lambda r: (r["status"], r["paper"].lower()))
    return rows


def write_change_log(output_folder: Path, logger: logging.Logger | None = None) -> Path:
    """Write change_log.csv to the output folder. Always writes a header row."""
    output_folder.mkdir(parents=True, exist_ok=True)
    rows = collect_change_log_rows(output_folder)
    path = output_folder / CHANGE_LOG_CSV

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CHANGE_LOG_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    if logger:
        logger.info("Change log saved: %s (%d paper(s) need attention)", path, len(rows))
    return path
