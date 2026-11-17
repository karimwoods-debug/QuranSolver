"""The problem-solving pipeline: safety -> retrieve -> explain -> verify."""

from __future__ import annotations

import logging
import re
import sqlite3
from typing import Any

from . import safety
from .config import Settings
from .llm import LLM, Guidance, LLMError
from .search import search
from .themes import match_themes

log = logging.getLogger(__name__)

# A quoted span this long in the model's explanation must appear verbatim in
# one of the cited texts, or the point is dropped.
_QUOTE = re.compile(r"[\"“]([^\"”]{20,})[\"”]")
_QUOTE_MIN_WORDS = 5


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", s.lower())).strip()


def _has_unverified_quote(text: str, cited_texts: list[str]) -> bool:
    haystack = " ".join(_norm(t) for t in cited_texts)
    for match in _QUOTE.finditer(text):
        quote = _norm(match.group(1))
        if len(quote.split()) >= _QUOTE_MIN_WORDS and quote not in haystack:
            return True
    return False


def verify_guidance(guidance: Guidance, sources: list[dict[str, Any]]) -> tuple[dict[str, Any], int]:
    """Keep only points whose citations all refer to retrieved texts.

    Returns (verified guidance as a dict, number of points dropped).
    """
    by_id = {s["id"]: s for s in sources}
    points = []
    dropped = 0
    for point in guidance.points:
        cited = [c for c in dict.fromkeys(point.citations) if c in by_id]
        invalid = [c for c in point.citations if c not in by_id]
        if invalid or not cited:
            log.warning("dropping point with unverifiable citations: %s", invalid or "none")
            dropped += 1
            continue
        if _has_unverified_quote(point.explanation, [by_id[c]["text_en"] for c in cited]):
            log.warning("dropping point containing an unverified quotation")
            dropped += 1
            continue
        points.append({"heading": point.heading, "explanation": point.explanation, "citations": cited})
    return (
        {"summary": guidance.summary, "points": points, "practical_steps": list(guidance.practical_steps)},
        dropped,
    )


def solve(conn: sqlite3.Connection, settings: Settings, problem: str, llm: LLM | None) -> dict[str, Any]:
    problem = problem.strip()
    check = safety.check(problem)
    themes = match_themes(problem)

    theme_names = [t.name for t in themes]
    if themes:
        # Curated terms only: the user's raw words ("argument", "fight")
        # pull in verses from unrelated contexts such as warfare.
        terms = [term for t in themes for term in t.terms]
    else:
        terms = problem.split()  # each word is its own OR-clause

    notices: list[str] = []
    mode = "search"
    if llm is not None:
        try:
            plan = llm.plan(problem)
            terms = plan.english_terms + plan.arabic_terms + [t for th in themes for t in th.terms]
            theme_names = list(dict.fromkeys(plan.themes + theme_names))
            check.crisis = check.crisis or plan.crisis
            check.needs_scholar = check.needs_scholar or plan.is_ruling_question
            mode = "guided"
        except LLMError as exc:
            log.warning("planning failed, falling back to keyword search: %s", exc)
            notices.append("Guided explanations are unavailable right now; showing search results only.")

    if check.crisis and not check.resources:
        check.resources = list(safety.CRISIS_RESOURCES)
    if check.needs_scholar and not check.scholar_note:
        check.scholar_note = safety.SCHOLAR_NOTE

    verses = search(conn, terms, "quran", settings.max_verses)
    hadith = search(conn, terms, "hadith", settings.max_hadith)
    sources = verses + hadith

    guidance = None
    if mode == "guided" and sources:
        try:
            raw = llm.explain(problem, sources)  # type: ignore[union-attr]
            guidance, dropped = verify_guidance(raw, sources)
            if dropped:
                notices.append(f"{dropped} point(s) were removed because their citations could not be verified.")
            cited = {c for p in guidance["points"] for c in p["citations"]}
            if cited:
                # Show only the texts the guidance relies on; uncited
                # retrieved texts may be out of context for this problem.
                verses = [d for d in verses if d["id"] in cited]
                hadith = [d for d in hadith if d["id"] in cited]
                for d in verses + hadith:
                    d["cited"] = True
            else:
                guidance = None
                mode = "search"
                notices.append("No verified guidance could be produced; showing search results only.")
        except LLMError as exc:
            log.warning("explanation failed: %s", exc)
            notices.append("Guided explanations are unavailable right now; showing search results only.")
            mode = "search"

    if not sources:
        notices.append(
            "No matching texts were found. Try describing the problem in different words "
            "(for example: patience, family, debt, grief)."
        )

    return {
        "mode": mode,
        "themes": theme_names,
        "crisis": check.crisis,
        "crisis_resources": check.resources,
        "needs_scholar": check.needs_scholar,
        "scholar_note": check.scholar_note,
        "guidance": guidance,
        "verses": verses,
        "hadith": hadith,
        "notices": notices,
    }
