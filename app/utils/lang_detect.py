def is_korean(text: str) -> bool:
    return any('가' <= ch <= '힣' for ch in text)
