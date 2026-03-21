# backend/multilingual.py
from deep_translator import GoogleTranslator

# Map human-friendly language names to GoogleTranslator codes
LANG_CODE_MAP = {
    "English": "en",
    "Hindi": "hi",
    "Sanskrit": "sa"
}

def translate_text(text, target_lang="English"):
    """
    Translate the given text to the target language using GoogleTranslator.
    - text: str, the text to translate
    - target_lang: str, "English", "Hindi", or "Sanskrit"
    Returns the translated text.
    """
    target_code = LANG_CODE_MAP.get(target_lang, "en")
    try:
        # GoogleTranslator automatically detects the source language
        translated = GoogleTranslator(source='auto', target=target_code).translate(text)
        return translated
    except Exception as e:
        return f"[Translation Error: {e}]"