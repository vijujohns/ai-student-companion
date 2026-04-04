"""
Translation utilities with language management.

Provides text translation (via deep_translator / Google Translate free API),
language detection, and a static catalogue of supported languages for the
multilingual tutoring UI.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Dict, List, Optional

try:
    from deep_translator import GoogleTranslator  # type: ignore
except ImportError:
    GoogleTranslator = None  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported languages catalogue
# Subset of languages commonly used in Indian + international education.
# Code → human-readable name (English).
# ---------------------------------------------------------------------------
SUPPORTED_LANGUAGES: Dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ur": "Urdu",
    "or": "Odia",
    "as": "Assamese",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "pt": "Portuguese",
    "ar": "Arabic",
    "zh-CN": "Chinese (Simplified)",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
}

# Phrases used as last-resort fallback when the translator is unreachable.
_FALLBACK_PHRASES: Dict[str, str] = {
    "namaste": "hello",
    "dhanyawad": "thank you",
}
_INDIC_LANGUAGE_CODES = {"hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "ur", "or", "as"}


def _indictrans2_enabled() -> bool:
    flag = str(os.getenv("ENABLE_INDIC_TRANS2", "")).strip().lower()
    return flag in {"1", "true", "yes", "on"}


@lru_cache(maxsize=2)
def _load_indictrans2_backend(direction: str):
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # type: ignore

    if direction == "en-indic":
        model_name = os.getenv("INDICTRANS2_EN_INDIC_MODEL", "ai4bharat/indictrans2-en-indic-1B")
    else:
        model_name = os.getenv("INDICTRANS2_INDIC_EN_MODEL", "ai4bharat/indictrans2-indic-en-1B")

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name, trust_remote_code=True)
    return tokenizer, model


def _translate_with_indictrans2(text: str, *, target: str, source: str = "auto") -> Optional[str]:
    if not _indictrans2_enabled() or not text or not text.strip():
        return None

    normalized_source = (source or "auto").strip().lower()
    use_en_to_indic = target in _INDIC_LANGUAGE_CODES and normalized_source in {"auto", "en"}
    use_indic_to_en = target == "en" and normalized_source in _INDIC_LANGUAGE_CODES

    if not use_en_to_indic and not use_indic_to_en:
        return None

    direction = "en-indic" if use_en_to_indic else "indic-en"

    try:
        tokenizer, model = _load_indictrans2_backend(direction)
        inputs = tokenizer(text, return_tensors="pt", truncation=True)
        outputs = model.generate(**inputs, max_new_tokens=256)
        decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)
        result = (decoded[0] if decoded else "").strip()
        return result or None
    except Exception as exc:
        logger.debug("IndicTrans2 translation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Core translation
# ---------------------------------------------------------------------------

def translate_text(
    text: str,
    target: str = "en",
    source: str = "auto",
) -> str:
    """
    Translate *text* to *target* language code.

    Falls back to the original text (with a log warning) when the translator
    is unavailable so callers always get a string back.

    Parameters
    ----------
    text   : str  — Text to translate.
    target : str  — BCP-47 / Google Translate language code (default ``"en"``).
    source : str  — Source language code; ``"auto"`` for auto-detection.

    Returns
    -------
    str — Translated text, or original text on failure.
    """
    if not text or not text.strip():
        return text

    # Normalise target — unknown codes fall back to English
    if target not in SUPPORTED_LANGUAGES:
        logger.warning("translate_text: unknown target language %r, falling back to 'en'", target)
        target = "en"

    # No-op when source and target are the same known language
    if source != "auto" and source == target:
        return text

    indic_result = _translate_with_indictrans2(text, target=target, source=source)
    if indic_result:
        return indic_result

    try:
        if GoogleTranslator is None:
            raise ImportError("deep_translator not installed")
        result = GoogleTranslator(source=source, target=target).translate(text)
        return result if result else text
    except Exception as exc:
        logger.warning("translate_text failed (target=%s): %s", target, exc)
        return _FALLBACK_PHRASES.get(text.strip().lower(), text)


def detect_language(text: str) -> Optional[str]:
    """
    Attempt to detect the language of *text*.

    Returns a BCP-47 language code string, or ``None`` if detection fails.
    """
    if not text or not text.strip():
        return None
    try:
        # GoogleTranslator doesn't expose detect directly; use a dummy translation and
        # read the detected source language from the response metadata.
        # As a lightweight approach, translate to English and let the API surface the source.
        if GoogleTranslator is None:
            raise ImportError("deep_translator not installed")
        translator = GoogleTranslator(source="auto", target="en")
        translator.translate(text[:200])
        # deep-translator ≥1.9 exposes source after translate
        detected = getattr(translator, "_source", None) or getattr(translator, "source", None)
        if detected and detected != "auto":
            return detected
    except Exception as exc:
        logger.debug("detect_language failed: %s", exc)
    return None


def list_languages() -> List[Dict[str, str]]:
    """Return the full list of supported languages as ``[{code, name}]``."""
    return [{"code": code, "name": name} for code, name in SUPPORTED_LANGUAGES.items()]


# ---------------------------------------------------------------------------
# Backward-compat alias (used by older call-sites)
# ---------------------------------------------------------------------------

def translate(text: str, target: str = "en") -> str:
    """Alias for :func:`translate_text` kept for backward compatibility."""
    return translate_text(text, target=target)
