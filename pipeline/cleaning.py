"""Text cleaning and normalization helpers for news analyzer."""

import re
from typing import List, Any
from core.config import settings

__all__ = [
    "truncate_text",
    "clean_and_validate_hashtags",
]


def truncate_text(
    text: str, max_len: int = settings.MAX_TEXT_LENGTH_FOR_ANALYSIS
) -> str:
    """Truncate text to max_len characters adding ellipsis."""
    return text if len(text) <= max_len else text[:max_len] + "..."


def clean_and_validate_hashtags(raw: List[Any]) -> List[str]:
    """Cleanup hashtags from model response and ensure uniqueness."""
    cleaned = []
    if not isinstance(raw, list):
        return []
    for tag in raw:
        if not isinstance(tag, str):
            continue
        tag_clean = re.sub(r"[^\w\s]", "", tag).strip().replace(" ", "_")
        if tag_clean:
            cleaned.append(tag_clean.lower())
    # deduplicate preserving order
    return list(dict.fromkeys(cleaned))
