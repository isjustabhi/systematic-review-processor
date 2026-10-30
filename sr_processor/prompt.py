"""Load coding prompts from Word documents."""

from pathlib import Path

FRAMEWORK_BRIEFING_FILENAME = "framework_briefing.txt"

_COMBINED_PREFIX = (
    "You have first studied a framework or methods paper. Use that briefing as "
    "conceptual background when you apply the coding instructions below. "
    "Do not replace the coding instructions or the required JSON output format. "
    "If the framework and the coding instructions conflict, follow the coding instructions."
)


def combine_framework_and_prompt(framework_briefing: str, coding_prompt: str) -> str:
    """Two-step system prompt: framework briefing, then the lab coding protocol."""
    briefing = (framework_briefing or "").strip()
    protocol = (coding_prompt or "").strip()
    if not briefing:
        return protocol
    return (
        f"{_COMBINED_PREFIX}\n\n"
        "=== FRAMEWORK BRIEFING (read this first) ===\n\n"
        f"{briefing}\n\n"
        "=== CODING INSTRUCTIONS (apply these to each paper) ===\n\n"
        f"{protocol}"
    )


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
