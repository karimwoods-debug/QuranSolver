"""Deterministic safety checks that run before anything else.

These do not depend on the LLM, so they still work when it is off or
unavailable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_CRISIS_PATTERNS = [
    r"\bsuicid\w*",
    r"\bkill (?:my ?self|myself)\b",
    r"\bend (?:my|it all|my life)\b",
    r"\bwant to die\b",
    r"\bdon'?t want to (?:live|be alive)\b",
    r"\bself[- ]?harm\w*",
    r"\b(?:hurt|cut|harm)(?:ing)? myself\b",
    r"\babus(?:e|ed|ing|ive)\b",
    r"\b(?:hits|hitting|beats|beating|beat) me\b",
    r"\bdomestic violence\b",
    r"\brap(?:e|ed)\b",
    r"\bsexual(?:ly)? assault\w*",
    r"\bin danger\b",
    r"\bthreaten(?:ed|ing|s)? (?:me|to kill)\b",
]

_RULING_PATTERNS = [
    r"\bis (?:it|this|that) (?:haram|halal|allowed|permissible|forbidden|sinful)\b",
    r"\b(?:haram|halal)\b",
    r"\bfatwa\b",
    r"\bruling\b",
    r"\bpermissib\w*",
    r"\bdivorce\b",
    r"\btalaq\b",
    r"\bkhula\b",
    r"\binheritance\b",
    r"\bzakat\b",
    r"\binterest\b|\briba\b|\bmortgage\b",
]

CRISIS_RESOURCES = [
    "If you are in immediate danger, call your local emergency number now.",
    "Find a free, confidential crisis line in your country at https://findahelpline.com.",
    "Please also reach out to someone you trust: a family member, friend, imam or counsellor.",
]

SCHOLAR_NOTE = (
    "Your question involves a religious ruling (fiqh). The texts below are shared "
    "for reflection, but they are not a fatwa. Please consult a qualified scholar "
    "who can consider your full circumstances."
)


@dataclass
class SafetyResult:
    crisis: bool = False
    needs_scholar: bool = False
    resources: list[str] = field(default_factory=list)
    scholar_note: str | None = None


def check(text: str) -> SafetyResult:
    lowered = text.lower()
    result = SafetyResult()
    if any(re.search(p, lowered) for p in _CRISIS_PATTERNS):
        result.crisis = True
        result.resources = list(CRISIS_RESOURCES)
    if any(re.search(p, lowered) for p in _RULING_PATTERNS):
        result.needs_scholar = True
        result.scholar_note = SCHOLAR_NOTE
    return result
