"""
OCR (Optical Character Recognition) module.

Extracts text from image files (JPEG, PNG, GIF, WEBP) using pytesseract + Pillow.
Degrades gracefully when Tesseract is not installed — returns empty string with
a logged warning so the indexing pipeline can still mark the file as processed.

Usage:
    text = extract_text_from_image("/path/to/image.png")
    status = get_ocr_status()  # {"available": True, "engine": "tesseract"}
"""

from __future__ import annotations

import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported image extensions / MIME types
# ---------------------------------------------------------------------------

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
}

_MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB safety cap

# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def _check_ocr_available() -> bool:
    """Return True if pytesseract and Tesseract binary are reachable."""
    try:
        import pytesseract  # noqa: F401
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


_OCR_AVAILABLE: bool | None = None  # lazy-initialised


def get_ocr_status() -> Dict[str, object]:
    """
    Return a dict describing OCR availability.

    {
        "available": bool,
        "engine":    "tesseract" | "none",
        "message":   str
    }
    """
    global _OCR_AVAILABLE
    if _OCR_AVAILABLE is None:
        _OCR_AVAILABLE = _check_ocr_available()

    if _OCR_AVAILABLE:
        return {"available": True, "engine": "tesseract", "message": "Tesseract OCR is available"}
    return {
        "available": False,
        "engine": "none",
        "message": (
            "Tesseract is not installed. Install it from https://github.com/UB-Mannheim/tesseract/wiki "
            "and add `pytesseract` + `Pillow` to requirements.txt to enable image OCR."
        ),
    }


# ---------------------------------------------------------------------------
# Public extraction API
# ---------------------------------------------------------------------------

def extract_text_from_image(file_path: str, lang: str = "eng") -> str:
    """
    Extract text from an image file using Tesseract OCR.

    Parameters
    ----------
    file_path : str
        Absolute path to a JPEG / PNG / GIF / WEBP file.
    lang : str
        Tesseract language code(s), e.g. ``"eng"``  or ``"eng+hin"``.

    Returns
    -------
    str
        Extracted text, or empty string if OCR is unavailable / fails.
    """
    file_path = os.path.realpath(file_path)
    if not os.path.isfile(file_path):
        logger.warning("OCR: file not found: %s", file_path)
        return ""

    file_size = os.path.getsize(file_path)
    if file_size > _MAX_IMAGE_BYTES:
        logger.warning("OCR: file too large (%d bytes), skipping: %s", file_size, file_path)
        return ""

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        logger.warning("OCR: unsupported extension %s for %s", ext, file_path)
        return ""

    status = get_ocr_status()
    if not status["available"]:
        logger.warning("OCR unavailable — install Tesseract to enable image text extraction.")
        return ""

    try:
        from PIL import Image  # type: ignore
        import pytesseract  # type: ignore

        image = Image.open(file_path)
        # Convert palette / RGBA modes to RGB for better Tesseract compatibility
        if image.mode in ("P", "RGBA", "LA"):
            image = image.convert("RGB")

        text = pytesseract.image_to_string(image, lang=lang)
        return text.strip()
    except Exception as exc:
        logger.error("OCR extraction failed for %s: %s", file_path, exc)
        return ""


def is_image_file(file_path: str) -> bool:
    """Return True if the file has a supported image extension."""
    return os.path.splitext(file_path)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
