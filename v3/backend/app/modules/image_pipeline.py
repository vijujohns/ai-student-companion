"""Compatibility-first OCR and image extraction helpers for Step 10.

The goal is to enrich image ingestion without changing existing routes:
- extract OCR text when available
- normalize noisy image text
- derive simple filename/context hints
- build a short study summary for downstream retrieval
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

from .model_manager import generate_response
from .ocr import extract_text_from_image

_STOPWORDS = {
    "image",
    "photo",
    "diagram",
    "notes",
    "note",
    "page",
    "scan",
    "img",
    "the",
    "and",
    "for",
    "with",
    "from",
    "into",
    "this",
    "that",
}
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _title_from_path(file_path: str) -> str:
    stem = os.path.splitext(os.path.basename(str(file_path or "image")))[0]
    cleaned = re.sub(r"[_\-]+", " ", stem).strip()
    return cleaned or "image"


def _normalize_text(text: str) -> str:
    cleaned = str(text or "").replace("\x00", " ")
    cleaned = cleaned.replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _derive_keywords(title: str, text: str, limit: int = 8) -> List[str]:
    words: List[str] = []
    for token in _TOKEN_RE.findall(f"{title} {text}".lower()):
        if len(token) < 3 or token in _STOPWORDS or token.isdigit():
            continue
        if token not in words:
            words.append(token)
        if len(words) >= limit:
            break
    return words


def _fallback_summary(title: str, text: str, keywords: List[str]) -> str:
    preview = _normalize_text(text).replace("\n", " ")
    if preview:
        preview = preview[:220].rstrip()
        if keywords:
            return f"This image is about {title} and highlights {', '.join(keywords[:4])}. OCR notes: {preview}"
        return f"This image is about {title}. OCR notes: {preview}"
    if keywords:
        return f"This image appears related to {title} and key ideas such as {', '.join(keywords[:4])}."
    return f"This image appears related to {title}."


def extract_image_content(file_path: str, model_name: Optional[str] = None, lang: str = "eng") -> Dict[str, object]:
    """Extract OCR text plus lightweight study metadata from an image file."""
    title = _title_from_path(file_path)
    ocr_text = _normalize_text(extract_text_from_image(file_path, lang=lang))
    keywords = _derive_keywords(title, ocr_text)

    if ocr_text:
        text = ocr_text
    elif keywords:
        text = f"Image title: {title}\nKeywords: {', '.join(keywords)}"
    else:
        text = f"Image title: {title}"

    summary = ""
    if ocr_text:
        prompt = (
            "Summarize the study-relevant information extracted from this image. "
            "Keep it short, factual, and student-friendly.\n\n"
            f"Image title: {title}\n"
            f"OCR text:\n{text}\n\n"
            "Summary:"
        )
        try:
            summary = _normalize_text(generate_response("", prompt, model_name=model_name, task="summary"))
        except Exception:
            summary = ""

    if not summary:
        summary = _fallback_summary(title, text, keywords)

    return {
        "title": title,
        "text": text,
        "summary": summary,
        "keywords": keywords,
        "modality": "image",
    }
