from typing import Optional
from langdetect import detect, detect_langs, DetectorFactory, LangDetectException

DetectorFactory.seed = 0

TARGET_LANGS = {
    "ko", 
    "en", 
    "ja", 
    "zh",
    "es", 
    "fr", 
    "de", 
    "it",
    "pt", 
}

MIN_LENGTH = 5

def detect_language(text: str) -> Optional[str]:
    text = text.strip()

    if len(text) < MIN_LENGTH:
        return None

    try:
        lang = detect(text)
        return lang if lang in TARGET_LANGS else None
    except LangDetectException:
        return None


def detect_language_with_prob(text: str, threshold: float = 0.80) -> Optional[str]:
    text = text.strip()

    if len(text) < MIN_LENGTH:
        return None

    try:
        langs = detect_langs(text)
        top = langs[0]

        if top.lang in TARGET_LANGS and top.prob >= threshold:
            return top.lang
        return None
    except LangDetectException:
        return None