"""Arabic text normalisation for search (never used for display)."""

from __future__ import annotations

import re

# Harakat, Qur'anic annotation marks, superscript alef, tatweel and the
# extended-A combining marks used by Uthmani script.
_DIACRITICS = re.compile(
    "[ؐ-ًؚ-ٰٟۖ-ۭ࣓-ࣿـ]"
)
_LETTER_MAP = str.maketrans(
    {
        "أ": "ا",  # أ -> ا
        "إ": "ا",  # إ -> ا
        "آ": "ا",  # آ -> ا
        "ٱ": "ا",  # ٱ -> ا
        "ى": "ي",  # ى -> ي
        "ة": "ه",  # ة -> ه
        "ؤ": "و",  # ؤ -> و
        "ئ": "ي",  # ئ -> ي
    }
)


def normalize_arabic(text: str) -> str:
    """Strip diacritics and unify letter variants so searches match."""
    text = _DIACRITICS.sub("", text)
    text = text.translate(_LETTER_MAP)
    return re.sub(r"\s+", " ", text).strip()
