from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")


def normalize_entity(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).lower()
    text = _WHITESPACE.sub(" ", text).strip()
    kept: list[str] = []
    for index, char in enumerate(text):
        if char == "-" and _is_internal_hyphen(text, index):
            kept.append(char)
            continue
        if unicodedata.category(char).startswith("P"):
            continue
        kept.append(char)
    return _WHITESPACE.sub(" ", "".join(kept)).strip()


def _is_internal_hyphen(text: str, index: int) -> bool:
    if index == 0 or index + 1 >= len(text):
        return False
    return text[index - 1].isalnum() and text[index + 1].isalnum()
