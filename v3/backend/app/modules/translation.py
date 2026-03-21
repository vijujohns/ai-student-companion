"""
Translation with fallback
"""

from deep_translator import GoogleTranslator

fallback_dict = {
    "namaste": "hello"
}

def translate(text, target="en"):
    try:
        return GoogleTranslator(source="auto", target=target).translate(text)
    except:
        return fallback_dict.get(text.lower(), text)