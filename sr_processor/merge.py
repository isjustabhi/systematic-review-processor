"""Merge CSVs from multiple batch folders (e.g. 300 papers in 10 batches)."""

import logging
from pathlib import Path


def merge_batch_csvs(batch_output_dirs: list[Path], output_csv: Path) -> Path:
    import pandas as pd

    frames = []
    for d in batch_output_dirs:
        csv_path = d / "systematic_review_results.csv"
        if csv_path.exists():
            frames.append(pd.read_csv(csv_path))
        else:
            logging.warning("No CSV in %s — run batch first", d)

    if not frames:
        raise FileNotFoundError("No batch CSV files found to merge")

    merged = pd.concat(frames, ignore_index=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_csv, index=False, na_rep="")
    logging.info("Merged %d rows -> %s", len(merged), output_csv)
    return output_csv
