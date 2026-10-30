"""Assemble JSON outputs into a CSV spreadsheet."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sr_processor.config import ProcessorConfig


def assemble_csv(config: ProcessorConfig, logger: logging.Logger) -> Path | None:
    try:
        import pandas as pd
    except ImportError:
        logger.warning("pandas required for CSV. Install: pip install pandas")
        return None

    json_files = sorted(config.output_folder.glob("*.json"))
    json_files = [f for f in json_files if not f.name.endswith("_ERROR.json")]

    records = []
    for path in json_files:
        try:
            data = json.loads(path.read_text())
            if data.get("parse_error"):
                data["_needs_review"] = True
            for key in config.list_fields:
                if isinstance(data.get(key), list):
                    data[key] = "; ".join(data[key]) if data[key] else ""
            records.append(data)
        except Exception as e:
            logger.warning("Skipping %s: %s", path.name, e)

    if not records:
        logger.warning("No JSON records for CSV.")
        return None

    df = pd.DataFrame(records)
    sort_cols = [c for c in ["eligible", "authors"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(by=sort_cols, na_position="last")

    config.csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.csv_path, index=False, na_rep="")
    logger.info("CSV saved: %s (%d rows)", config.csv_path, len(df))
    return config.csv_path
