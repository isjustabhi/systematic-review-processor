#!/usr/bin/env python3
"""
Systematic Review PDF Processor — CLI (up to 400 papers per run).

Usage:
  python systematic_review_processor.py \\
    --pdf-folder ./papers --output-folder ./output \\
    --prompt-file ./Claude_Code_Prompting_v4.docx

  python run_review.py   # same defaults for the whole Pilot Papers folder
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from sr_processor.batch import run_batch
from sr_processor.config import ProcessorConfig

MAX_PAPERS = 400
DEFAULT_WORKERS = 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Systematic Review PDF Processor (max 400 papers)")
    parser.add_argument("--pdf-folder", required=True, help="Folder with PDF files")
    parser.add_argument("--output-folder", required=True, help="Folder for JSON + CSV output")
    parser.add_argument("--prompt-file", required=True, help="Coding prompt (.docx)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Parallel workers (default: 2)")
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Anthropic model id")
    parser.add_argument("--no-csv", action="store_true", help="Skip CSV assembly")
    parser.add_argument("--retry-failed", action="store_true", help="Only retry failed/parse-error papers")
    args = parser.parse_args()

    pdf_folder = Path(args.pdf_folder)
    output_folder = Path(args.output_folder)
    prompt_file = Path(args.prompt_file)

    if not pdf_folder.is_dir():
        print(f"ERROR: PDF folder not found: {pdf_folder}", file=sys.stderr)
        return 1
    if not prompt_file.is_file():
        print(f"ERROR: Prompt file not found: {prompt_file}", file=sys.stderr)
        return 1

    pdfs = sorted(pdf_folder.glob("*.pdf"))
    if not pdfs:
        print(f"ERROR: No PDFs in {pdf_folder}", file=sys.stderr)
        return 1
    if len(pdfs) > MAX_PAPERS:
        print(
            f"ERROR: Found {len(pdfs)} PDFs; this tool is configured for at most {MAX_PAPERS} per run.",
            file=sys.stderr,
        )
        return 1

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = input("Enter Anthropic API key: ").strip()
    if not api_key:
        print("ERROR: No API key.", file=sys.stderr)
        return 1

    config = ProcessorConfig(
        pdf_folder=pdf_folder,
        output_folder=output_folder,
        prompt_file=prompt_file,
        model=args.model,
        max_workers=max(1, min(args.workers, 4)),
        max_pdfs=MAX_PAPERS,
    )

    if args.retry_failed:
        print("Retry mode: only pending, failed, and parse-error papers will run.")

    try:
        result = run_batch(config, api_key=api_key, assemble=not args.no_csv)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print("\n--- Summary ---")
    print(f"Total PDFs:     {result.total}")
    print(f"Successful:     {result.successful}")
    print(f"Parse errors:   {result.parse_errors}")
    print(f"Failed:         {result.failed}")
    print(f"Skipped:        {result.skipped}")
    if result.csv_path:
        print(f"CSV:            {result.csv_path}")
    print(f"Output folder:  {output_folder}")

    if result.failed > 0:
        print("\nTip: Fix rate limits with --workers 1, delete *_ERROR.json, rerun.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
