"""Full-text retrieval over the verified corpus (SQLite FTS5, BM25 ranking)."""

from __future__ import annotations

import re
import sqlite3
from typing import Any, Iterable

from . import db
from .arabic import normalize_arabic

_STOPWORDS = {
    "a", "about", "after", "all", "am", "an", "and", "any", "are", "as", "at",
    "be", "because", "been", "but", "by", "can", "could", "did", "do", "does",
    "doing", "dont", "for", "from", "get", "got", "had", "has", "have", "he",
    "her", "him", "his", "how", "i", "if", "im", "in", "into", "is", "it",
    "its", "ive", "just", "keep", "know", "like", "me", "my", "myself", "not",
    "now", "of", "on", "or", "our", "out", "really", "she", "so", "some",
    "that", "the", "their", "them", "then", "there", "they", "this", "to",
    "too", "very", "was", "we", "what", "when", "which", "who", "why", "will",
    "with", "would", "you", "your", "feel", "feeling", "help", "want",
    "allah", "god",  # appear in nearly every text; they add noise, not signal
}

_WORD = re.compile(r"[A-Za-z]+|[ء-ي]+")


def _terms_from(text: str) -> list[str]:
    out = []
    for w in _WORD.findall(text):
        if w.isascii():
            w = w.lower()
            if w in _STOPWORDS or len(w) < 3:
                continue
        else:
            w = normalize_arabic(w)
            if len(w) < 2:
                continue
        out.append(w)
    return out


def build_match_query(terms: Iterable[str]) -> str | None:
    """Turn free-form terms/phrases into a safe FTS5 OR-query."""
    clauses: list[str] = []
    seen: set[str] = set()
    for term in terms:
        words = _terms_from(term)
        if not words:
            continue
        clause = '"' + " ".join(words) + '"'
        if clause not in seen:
            seen.add(clause)
            clauses.append(clause)
    return " OR ".join(clauses) if clauses else None


def search(
    conn: sqlite3.Connection, terms: Iterable[str], kind: str, limit: int
) -> list[dict[str, Any]]:
    """Return documents of `kind` ('quran' or 'hadith') ranked by BM25."""
    query = build_match_query(terms)
    if query is None:
        return []
    rows = conn.execute(
        "SELECT doc_id, bm25(search_index, 0.0, 0.0, 1.0, 1.0) AS score"
        " FROM search_index WHERE search_index MATCH ? AND kind = ?"
        " ORDER BY score LIMIT ?",
        (query, kind, limit),
    ).fetchall()
    docs = []
    for row in rows:
        doc = db.get_document(conn, row["doc_id"])
        if doc is not None:  # get_document re-checks authenticity
            doc["score"] = round(-row["score"], 3)
            docs.append(doc)
    return docs
