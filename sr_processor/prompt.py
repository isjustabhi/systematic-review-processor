"""Load coding prompts from Word documents."""

from pathlib import Path


def load_prompt_from_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as e:
        raise ImportError("python-docx required: pip install python-docx") from e

    doc = Document(str(path))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if not text.strip():
        raise ValueError(f"Prompt file appears empty: {path}")
    return text
