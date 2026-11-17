#!/usr/bin/env python3
"""Download the Qur'an and hadith collections and build the SQLite database.

Sources (open datasets on GitHub, compiled by fawazahmed0):
  Qur'an:  https://github.com/fawazahmed0/quran-api   (Arabic text originally from Tanzil.net)
  Hadith:  https://github.com/fawazahmed0/hadith-api (with per-hadith grades)

Usage:
  python scripts/import_data.py                     # all defaults
  python scripts/import_data.py --translation eng-sahih
  python scripts/import_data.py --collections bukhari muslim

Downloads are cached in data/raw/ so re-runs are fast.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from quransolver import db  # noqa: E402
from quransolver.authenticity import classify  # noqa: E402

QURAN_BASE = "https://raw.githubusercontent.com/fawazahmed0/quran-api/1"
HADITH_BASE = "https://raw.githubusercontent.com/fawazahmed0/hadith-api/1"

COLLECTIONS = {
    "bukhari": "Sahih al-Bukhari",
    "muslim": "Sahih Muslim",
    "abudawud": "Sunan Abi Dawud",
    "tirmidhi": "Jami' at-Tirmidhi",
    "nasai": "Sunan an-Nasa'i",
    "ibnmajah": "Sunan Ibn Majah",
}


def fetch_json(url: str, cache_dir: Path) -> dict:
    cache = cache_dir / url.split("/1/", 1)[1].replace("/", "__")
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    for attempt in range(4):
        try:
            print(f"  downloading {url}")
            with urllib.request.urlopen(url, timeout=120) as resp:
                data = resp.read().decode("utf-8")
            cache.write_text(data, encoding="utf-8")
            return json.loads(data)
        except OSError as exc:
            if attempt == 3:
                raise
            wait = 2 ** (attempt + 1)
            print(f"  failed ({exc}); retrying in {wait}s")
            time.sleep(wait)
    raise AssertionError("unreachable")


def import_quran(conn, cache: Path, arabic: str, translation: str) -> None:
    print("Qur'an:")
    info = fetch_json(f"{QURAN_BASE}/info.json", cache)
    ar = fetch_json(f"{QURAN_BASE}/editions/{arabic}.min.json", cache)["quran"]
    en = fetch_json(f"{QURAN_BASE}/editions/{translation}.min.json", cache)["quran"]

    db.insert_surahs(
        conn,
        (
            {
                "number": ch["chapter"],
                "name_translit": ch["name"],
                "name_en": ch["englishname"],
                "name_ar": ch["arabicname"],
                "revelation": ch.get("revelation"),
            }
            for ch in info["chapters"]
        ),
    )
    en_map = {(v["chapter"], v["verse"]): v["text"] for v in en}
    if len(ar) != 6236 or len(en_map) != 6236:
        raise SystemExit(f"Unexpected verse count: arabic={len(ar)} translation={len(en_map)}")
    n = db.insert_verses(
        conn,
        (
            {"surah": v["chapter"], "ayah": v["verse"], "text_ar": v["text"], "text_en": en_map[(v["chapter"], v["verse"])]}
            for v in ar
        ),
    )
    db.set_meta(conn, "quran_arabic", f"{arabic} via github.com/fawazahmed0/quran-api")
    db.set_meta(conn, "quran_translation", f"{translation} via github.com/fawazahmed0/quran-api")
    print(f"  {n} verses")


def import_collection(conn, cache: Path, key: str) -> None:
    name = COLLECTIONS[key]
    print(f"{name}:")
    en = fetch_json(f"{HADITH_BASE}/editions/eng-{key}.min.json", cache)
    ar = fetch_json(f"{HADITH_BASE}/editions/ara-{key}.min.json", cache)
    sections = en["metadata"].get("sections", {})
    ar_map = {int(h["hadithnumber"]): h["text"] for h in ar["hadiths"] if h.get("text", "").strip()}

    def rows():
        seen = set()
        for h in en["hadiths"]:
            text = (h.get("text") or "").strip()
            number = int(h["hadithnumber"])
            if not text or number in seen:
                continue
            seen.add(number)
            book = (h.get("reference") or {}).get("book")
            grade, graded_by, authentic = classify(key, book, h.get("grades") or [])
            yield {
                "collection": key,
                "collection_name": name,
                "number": number,
                "book": book,
                "book_name": sections.get(str(book)) or None,
                "text_en": text,
                "text_ar": ar_map.get(number),
                "grade": grade,
                "graded_by": graded_by,
                "is_authentic": authentic,
            }

    total, authentic = db.insert_hadith(conn, rows())
    print(f"  {total} hadith, {authentic} accepted as authentic")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("QURANSOLVER_DB", ROOT / "data" / "quransolver.db")))
    parser.add_argument("--arabic", default="ara-quransimple", help="Arabic Qur'an edition (default: ara-quransimple)")
    parser.add_argument(
        "--translation",
        default="eng-abdullahyusufal",
        help="English Qur'an edition (default: eng-abdullahyusufal). Check the translation's licence before publishing.",
    )
    parser.add_argument("--collections", nargs="+", default=list(COLLECTIONS), choices=list(COLLECTIONS))
    args = parser.parse_args()

    cache = ROOT / "data" / "raw"
    cache.mkdir(parents=True, exist_ok=True)
    args.db.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.db.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)

    conn = db.connect(tmp)
    db.init_db(conn)
    import_quran(conn, cache, args.arabic, args.translation)
    for key in args.collections:
        import_collection(conn, cache, key)
    db.set_meta(conn, "hadith", "github.com/fawazahmed0/hadith-api (grades: see quransolver/authenticity.py)")
    conn.commit()
    conn.execute("INSERT INTO search_index(search_index) VALUES ('optimize')")
    conn.commit()
    conn.close()
    tmp.replace(args.db)
    print(f"Done: {args.db}")


if __name__ == "__main__":
    main()
