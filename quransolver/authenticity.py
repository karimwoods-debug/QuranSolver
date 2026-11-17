"""Hadith authenticity rules.

The app only ever shows hadith that pass `is_authentic`. The rules are
deliberately conservative: when in doubt, a narration is excluded.

* Sahih al-Bukhari and Sahih Muslim: accepted as a whole (scholarly
  consensus on their main content), except the introduction of Sahih Muslim
  (book 0), which is mostly statements of scholars rather than the graded
  core of the collection.
* The four Sunan (Abu Dawud, Tirmidhi, Nasa'i, Ibn Majah): accepted only
  when al-Albani's grade is a plain Sahih/Hasan grade for a marfu' hadith.
  Grades that only authenticate the chain ("Isnaad"), mark the narration as
  a Companion's or Successor's statement (Mauquf/Maqtu), or as weak,
  rejected, anomalous or fabricated, are excluded. Narrations with no grade
  from al-Albani are excluded.

These rules should be reviewed by a qualified scholar before launch.
"""

from __future__ import annotations

SAHIHAYN = {"bukhari", "muslim"}
SUNAN = {"abudawud", "tirmidhi", "nasai", "ibnmajah"}
PRIMARY_GRADER = "Al-Albani"

# Every word of the grade must be one of these for it to count as authentic.
_ACCEPTED_GRADE_WORDS = {"sahih", "hasan", "hadith", "mutawatir", "lighairihi", "matn"}


def grade_is_authentic(grade: str | None) -> bool:
    if not grade:
        return False
    words = grade.lower().replace("-", " ").split()
    if not words or words[0] not in {"sahih", "hasan"}:
        return False
    return all(word in _ACCEPTED_GRADE_WORDS for word in words)


def classify(collection: str, book: int | None, grades: list[dict]) -> tuple[str, str, bool]:
    """Return (grade_label, graded_by, is_authentic) for one hadith."""
    if collection in SAHIHAYN:
        if collection == "muslim" and book == 0:
            return ("Introduction (not graded)", "", False)
        return ("Sahih", "Collection", True)

    if collection in SUNAN:
        for g in grades:
            if g.get("name") == PRIMARY_GRADER:
                grade = g.get("grade", "").strip()
                return (grade, PRIMARY_GRADER, grade_is_authentic(grade))
        return ("Ungraded", "", False)

    return ("Ungraded", "", False)
