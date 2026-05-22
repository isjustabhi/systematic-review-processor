#!/usr/bin/env python3
"""CLI runner — processes PDFs in ./RAG Pilot Papers (max 20)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAPERS = ROOT / "RAG Pilot Papers"
OUTPUT = ROOT / "output"
PROMPT = ROOT / "Claude_Code_Prompting_v4.docx"


def main() -> int:
    if not PROMPT.is_file():
        print(f"Missing prompt: {PROMPT}", file=sys.stderr)
        print("Add Claude_Code_Prompting_v4.docx to the project folder.", file=sys.stderr)
        return 1

    pdfs = sorted(PAPERS.glob("*.pdf")) if PAPERS.is_dir() else []
    if not pdfs:
        print(f"No PDFs in: {PAPERS}", file=sys.stderr)
        return 1

    print(f"Running systematic review on {len(pdfs)} PDF(s) (max 20)...")

    extra = [a for a in sys.argv[1:] if a.startswith("-")]
    sys.argv = [
        "systematic_review_processor.py",
        "--pdf-folder",
        str(PAPERS),
        "--output-folder",
        str(OUTPUT),
        "--prompt-file",
        str(PROMPT),
        "--workers",
        "1",
        *extra,
    ]
    from systematic_review_processor import main as cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
