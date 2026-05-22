"""PDF text extraction."""

from pathlib import Path

import pypdf


def extract_pdf_text(pdf_path: Path) -> str:
    try:
        with pdf_path.open("rb") as f:
            reader = pypdf.PdfReader(f)
            pages = [p.extract_text() for p in reader.pages if p.extract_text()]
        text = "\n\n".join(pages)
        if not text.strip():
            raise ValueError("No text could be extracted from PDF (scanned image?).")
        return text
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from {pdf_path.name}: {e}") from e
