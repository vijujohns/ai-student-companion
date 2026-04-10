"""Shared query classification helpers for RAG, prompting, and formatting."""

from __future__ import annotations

import re

_ALLOWED_LABELS = {"fact", "definition", "explanation", "list", "quote", "math", "summary_structured", "general"}


def _normalize_query(query: str) -> str:
    raw = str(query or "")
    primary = raw.split("Tutor guidance:", 1)[0]
    primary = primary.split("Recent conversation:", 1)[0]
    return " ".join(primary.strip().lower().split())


def classify_query(query: str) -> str:
    """Return one stable label for the user's query across the whole pipeline."""
    normalized = _normalize_query(query)
    if not normalized:
        return "general"

    if any(term in normalized for term in ("solve", "equation", "formula", "calculate", "derive", "find x", "step by step")):
        return "math"

    if re.search(
        r"^(?:what did|who said|who wrote|what was written|quote|quoted|which line|what did .+ write|what did .+ say)\b",
        normalized,
    ):
        return "quote"

    if re.search(
        r"^(?:summari[sz]e|give (?:me )?(?:a )?(?:summary|brief summary|quick summary|overview)|prepare (?:revision )?notes|make (?:revision )?notes|create (?:revision )?notes)\b",
        normalized,
    ) or any(
        phrase in normalized
        for phrase in (
            "revision notes",
            "study notes",
            "short notes",
            "summary of",
            "overview of",
            "notes on",
            "key points of",
        )
    ):
        return "summary_structured"

    if re.search(r"^(?:list|name|show|give|mention)\b", normalized) or any(
        phrase in normalized
        for phrase in (
            "characteristics of",
            "properties of",
            "features of",
            "types of",
            "parts of",
            "examples of",
            "uses of",
        )
    ):
        return "list"

    if "what is" in normalized or re.search(r"\bdefine\b|\bmeaning of\b", normalized):
        return "definition"

    if re.search(r"^(?:who|when|where|which|how many|what was|what were|what are)\b", normalized):
        return "fact"

    if any(term in normalized for term in ("explain", "why", "how", "describe", "teach me", "help me")):
        return "explanation"

    return "general"


__all__ = ["classify_query"]
