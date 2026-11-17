"""SQLite storage: the verified corpus and its full-text index.

Document IDs are stable strings used everywhere (API, LLM citations):
  Qur'an: "Q:<surah>:<ayah>"            e.g. "Q:2:153"
  Hadith: "H:<collection>:<number>"     e.g. "H:bukhari:6018"
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .arabic import normalize_arabic

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS surahs (
    number         INTEGER PRIMARY KEY,
    name_translit  TEXT NOT NULL,
    name_en        TEXT NOT NULL,
    name_ar        TEXT NOT NULL,
    revelation     TEXT
);

CREATE TABLE IF NOT EXISTS verses (
    id       TEXT PRIMARY KEY,
    surah    INTEGER NOT NULL REFERENCES surahs(number),
    ayah     INTEGER NOT NULL,
    text_ar  TEXT NOT NULL,
    text_en  TEXT NOT NULL,
    UNIQUE (surah, ayah)
);

CREATE TABLE IF NOT EXISTS hadith (
    id               TEXT PRIMARY KEY,
    collection       TEXT NOT NULL,
    collection_name  TEXT NOT NULL,
    number           INTEGER NOT NULL,
    book             INTEGER,
    book_name        TEXT,
    text_en          TEXT NOT NULL,
    text_ar          TEXT,
    grade            TEXT NOT NULL,
    graded_by        TEXT NOT NULL,
    is_authentic     INTEGER NOT NULL
);

-- Only Qur'an verses and AUTHENTIC hadith are indexed, so weak or
-- ungraded narrations can never come back from a search.
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    doc_id UNINDEXED,
    kind UNINDEXED,
    text_en,
    text_ar,
    tokenize = 'porter unicode61 remove_diacritics 2'
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))


def get_meta(conn: sqlite3.Connection) -> dict[str, str]:
    return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM meta")}


def verse_id(surah: int, ayah: int) -> str:
    return f"Q:{surah}:{ayah}"


def hadith_id(collection: str, number: int) -> str:
    return f"H:{collection}:{number}"


def insert_surahs(conn: sqlite3.Connection, rows: Iterable[dict[str, Any]]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO surahs (number, name_translit, name_en, name_ar, revelation)"
        " VALUES (:number, :name_translit, :name_en, :name_ar, :revelation)",
        list(rows),
    )


def insert_verses(conn: sqlite3.Connection, rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    for r in rows:
        vid = verse_id(r["surah"], r["ayah"])
        conn.execute(
            "INSERT OR REPLACE INTO verses (id, surah, ayah, text_ar, text_en) VALUES (?, ?, ?, ?, ?)",
            (vid, r["surah"], r["ayah"], r["text_ar"], r["text_en"]),
        )
        conn.execute(
            "INSERT INTO search_index (doc_id, kind, text_en, text_ar) VALUES (?, 'quran', ?, ?)",
            (vid, r["text_en"], normalize_arabic(r["text_ar"])),
        )
        count += 1
    return count


def insert_hadith(conn: sqlite3.Connection, rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
    """Insert hadith rows; returns (total, authentic)."""
    total = authentic = 0
    for r in rows:
        hid = hadith_id(r["collection"], r["number"])
        conn.execute(
            "INSERT OR REPLACE INTO hadith (id, collection, collection_name, number, book, book_name,"
            " text_en, text_ar, grade, graded_by, is_authentic) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                hid,
                r["collection"],
                r["collection_name"],
                r["number"],
                r.get("book"),
                r.get("book_name"),
                r["text_en"],
                r.get("text_ar"),
                r["grade"],
                r["graded_by"],
                1 if r["is_authentic"] else 0,
            ),
        )
        total += 1
        if r["is_authentic"]:
            authentic += 1
            conn.execute(
                "INSERT INTO search_index (doc_id, kind, text_en, text_ar) VALUES (?, 'hadith', ?, ?)",
                (hid, r["text_en"], normalize_arabic(r.get("text_ar") or "")),
            )
    return total, authentic


def get_verse(conn: sqlite3.Connection, vid: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT v.id, v.surah, v.ayah, v.text_ar, v.text_en,"
        " s.name_translit, s.name_en, s.name_ar"
        " FROM verses v JOIN surahs s ON s.number = v.surah WHERE v.id = ?",
        (vid,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "kind": "quran",
        "text_ar": row["text_ar"],
        "text_en": row["text_en"],
        "reference": f"Qur'an {row['surah']}:{row['ayah']}",
        "source": f"Surah {row['name_translit']} ({row['name_en']}) {row['surah']}:{row['ayah']}",
        "surah_name_ar": row["name_ar"],
        "url": f"https://quran.com/{row['surah']}/{row['ayah']}",
    }


def get_hadith(conn: sqlite3.Connection, hid: str, authentic_only: bool = True) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM hadith WHERE id = ?", (hid,)).fetchone()
    if row is None or (authentic_only and not row["is_authentic"]):
        return None
    grade = row["grade"]
    if row["graded_by"] and row["graded_by"] != "Collection":
        grade = f"{grade} ({row['graded_by']})"
    return {
        "id": row["id"],
        "kind": "hadith",
        "text_ar": row["text_ar"],
        "text_en": row["text_en"],
        "reference": f"{row['collection_name']} {row['number']}",
        "source": f"{row['collection_name']}, Book: {row['book_name'] or row['book']}",
        "grade": grade,
        "url": None,
    }


def get_document(conn: sqlite3.Connection, doc_id: str) -> dict[str, Any] | None:
    if doc_id.startswith("Q:"):
        return get_verse(conn, doc_id)
    if doc_id.startswith("H:"):
        return get_hadith(conn, doc_id)
    return None


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "verses": conn.execute("SELECT COUNT(*) FROM verses").fetchone()[0],
        "hadith_total": conn.execute("SELECT COUNT(*) FROM hadith").fetchone()[0],
        "hadith_authentic": conn.execute(
            "SELECT COUNT(*) FROM hadith WHERE is_authentic = 1"
        ).fetchone()[0],
    }
