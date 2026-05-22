"""
Coding schema for Claude_Code_Prompting_v4.docx (social connectedness systematic review).

Single source of truth for JSON keys, CSV column order, and light validation.
Must stay aligned with the OUTPUT FORMAT section in the prompt document.
"""

from __future__ import annotations

from typing import Any

PROMPT_VERSION = "Claude_Code_Prompting_v4"
PROMPT_FILENAME = "Claude_Code_Prompting_v4.docx"

# Eligibility (prompt: STUDY ELIGIBILITY section)
ELIGIBILITY_RULES = (
    "Manipulation of social connection (not only measured)",
    "True experiment or RCT with between-subjects randomization",
    "At least one health-relevant outcome (behavior, biomarker, or clinical endpoint)",
    "Peer-reviewed journal article or dissertation (not conference proceedings)",
)

# Fields returned by Claude (exact keys from prompt OUTPUT FORMAT)
CODING_FIELDS: tuple[str, ...] = (
    "eligible",
    "reason",
    "publication_year",
    "title",
    "publication_title",
    "apa_citation",
    "type_of_study",
    "country",
    "state",
    "region",
    "country_outside_us",
    "publishing_method",
    "sample_size",
    "pct_female",
    "mean_age",
    "age_distribution",
    "pct_minority",
    "clinical_population",
    "clinical_population_specify",
    "target_sfq",
    "secondary_target_sfq",
    "connection_measure",
    "delivery_modality",
    "target_group",
    "intervention_partner",
    "intervention_partner_other",
    "duration_intensity",
    "theoretical_basis",
    "health_behavior_studied",
    "health_behavior",
    "health_biomarker_studied",
    "health_biomarker",
    "clinical_endpoint_studied",
    "clinical_endpoint",
    "define_primary",
    "direction_of_outcome",
    "notes",
    "authors",
    "confidence",
    "needs_human_review",
    "review_reason",
)

LIST_FIELDS: tuple[str, ...] = (
    "health_behavior",
    "health_biomarker",
    "clinical_endpoint",
)

# Added by the processor (not from the model)
RUN_METADATA_FIELDS: tuple[str, ...] = (
    "_source_file",
    "_model",
    "_processed_timestamp",
)

CSV_COLUMN_ORDER: tuple[str, ...] = CODING_FIELDS + (
    "_source_file",
    "_needs_review",
    "_validation_warnings",
)

ENUM_HINTS: dict[str, tuple[str, ...]] = {
    "type_of_study": ("Lab-Based", "RCT", "Other"),
    "country": ("US", "Outside US"),
    "region": ("Northeast", "Midwest", "South", "West"),
    "target_sfq": ("S", "F", "Q"),
    "secondary_target_sfq": ("S", "F", "Q"),
    "direction_of_outcome": ("positive", "negative", "null", "mixed"),
    "clinical_population": ("Yes", "No"),
    "duration_intensity": ("Single session", ">1 session"),
}


def build_user_message(pdf_text: str) -> str:
    """User turn: remind model of strict JSON contract + paper text."""
    keys_preview = ", ".join(CODING_FIELDS[:8]) + ", … (all fields in system prompt)"
    return (
        "Code this paper using the systematic review instructions in the system prompt. "
        "Reply with ONE valid JSON object only — no markdown fences or commentary. "
        f"Required keys include: {keys_preview}. "
        "If ineligible, set eligible=false, fill reason and title if known, other fields null or [].\n\n"
        "--- PAPER TEXT ---\n\n"
        + pdf_text
    )


def validate_coding(data: dict[str, Any]) -> list[str]:
    """Return human-readable validation warnings (empty if OK)."""
    warnings: list[str] = []

    if "eligible" not in data:
        warnings.append("Missing required key: eligible")
        return warnings

    if not isinstance(data.get("eligible"), bool):
        warnings.append("eligible must be true or false")

    conf = data.get("confidence")
    if conf is not None:
        try:
            c = float(conf)
            if c < 0 or c > 1:
                warnings.append("confidence must be between 0.0 and 1.0")
        except (TypeError, ValueError):
            warnings.append("confidence must be a number")

    if data.get("eligible"):
        if not data.get("title"):
            warnings.append("Eligible study missing title")
        sfq = data.get("target_sfq")
        if sfq and sfq not in ENUM_HINTS["target_sfq"]:
            warnings.append(f"target_sfq unexpected value: {sfq}")
    else:
        if not data.get("reason"):
            warnings.append("Ineligible study should include reason")

    for field, allowed in ENUM_HINTS.items():
        val = data.get(field)
        if val is not None and val != "" and val not in allowed:
            if field == "secondary_target_sfq":
                continue
            warnings.append(f"{field}={val!r} not in {allowed}")

    if data.get("needs_human_review") and not data.get("review_reason"):
        warnings.append("needs_human_review=true but review_reason empty")

    return warnings
