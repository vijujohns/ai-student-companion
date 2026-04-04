"""Compatibility-first translation executor for Step 11."""

from __future__ import annotations

import re
from typing import Optional

from .translation import SUPPORTED_LANGUAGES, translate_text

_LANGUAGE_NAME_TO_CODE = {name.lower(): code for code, name in SUPPORTED_LANGUAGES.items()}
_LANGUAGE_NAME_TO_CODE.update({
    "english": "en",
    "hindi": "hi",
    "bengali": "bn",
    "tamil": "ta",
    "telugu": "te",
    "marathi": "mr",
    "gujarati": "gu",
    "kannada": "kn",
    "malayalam": "ml",
    "punjabi": "pa",
    "urdu": "ur",
    "odia": "or",
    "assamese": "as",
})

_TRANSLATE_PATTERNS = [
    re.compile(r'^\s*translate\s+["\']?(?P<text>.+?)["\']?\s+to\s+(?P<lang>[a-zA-Z ()-]+)\s*$', re.IGNORECASE),
    re.compile(r'^\s*["\']?(?P<text>.+?)["\']?\s+in\s+(?P<lang>[a-zA-Z ()-]+)\s*$', re.IGNORECASE),
]


def _normalize_language_code(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "en"
    if raw in SUPPORTED_LANGUAGES:
        return raw
    lowered = raw.lower()
    return _LANGUAGE_NAME_TO_CODE.get(lowered, "en")


def _extract_translation_request(query: str) -> tuple[str, str]:
    text = str(query or "").strip()
    if not text:
        return "", "en"

    for pattern in _TRANSLATE_PATTERNS:
        match = pattern.match(text)
        if match:
            source_text = match.group("text").strip().strip('"\'')
            target = _normalize_language_code(match.group("lang"))
            return source_text, target

    return text, "en"


def execute_translation_task(
    *,
    query: str,
    user_id: str,
    session_id: str,
    model_name: Optional[str] = None,
    content_id: Optional[str] = None,
) -> str:
    """Translate a routed chat request using the shared translation stack."""
    source_text, target = _extract_translation_request(query)
    translated = translate_text(source_text, target=target, source="auto")
    language_name = SUPPORTED_LANGUAGES.get(target, target)
    return f"Translation ({language_name}): {translated}".strip()
