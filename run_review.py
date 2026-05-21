#!/usr/bin/env python3
"""One-command runner for your 20 papers in ./papers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAPERS = ROOT / "papers"
OUTPUT = ROOT / "output"
PROMPT = ROOT / "Claude_Code_Prompting_v4.docx"


def main() -> int:
    if not PAPERS.is_dir():
        print(f"Missing folder: {PAPERS}", file=sys.stderr)
        return 1
    if not PROMPT.is_file():
        print(f"Missing prompt: {PROMPT}", file=sys.stderr)
        return 1

    n = len(list(PAPERS.glob("*.pdf")))
    print(f"Running systematic review on {n} PDF(s) (max 20)...")

    sys.argv = [
        "systematic_review_processor.py",
        "--pdf-folder",
        str(PAPERS),
        "--output-folder",
        str(OUTPUT),
        "--prompt-file",
        str(PROMPT),
        "--workers",
        "2",
        *sys.argv[1:],
    ]
    from systematic_review_processor import main as cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
