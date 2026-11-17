"""Test fixtures.

The corpus here is SYNTHETIC placeholder text. It is not scripture, so tests
never risk asserting a misquoted verse or hadith.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from quransolver import db
from quransolver.api import create_app
from quransolver.authenticity import classify
from quransolver.config import Settings


def _hadith(collection, name, number, text, grades=None, book=1):
    grade, by, ok = classify(collection, book, grades or [])
    return {
        "collection": collection,
        "collection_name": name,
        "number": number,
        "book": book,
        "book_name": "Test Book",
        "text_en": text,
        "text_ar": "نص تجريبي",
        "grade": grade,
        "graded_by": by,
        "is_authentic": ok,
    }


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.init_db(c)
    db.insert_surahs(c, [
        {"number": 1, "name_translit": "Test-One", "name_en": "The First", "name_ar": "الأولى", "revelation": "Mecca"},
        {"number": 2, "name_translit": "Test-Two", "name_en": "The Second", "name_ar": "الثانية", "revelation": "Medina"},
    ])
    db.insert_verses(c, [
        {"surah": 1, "ayah": 1, "text_ar": "الصَّبْرُ نَصٌّ تَجْرِيبِيٌّ", "text_en": "PLACEHOLDER verse about patience and trust in hardship."},
        {"surah": 1, "ayah": 2, "text_ar": "نص تجريبي", "text_en": "PLACEHOLDER verse about kindness to parents and kinship."},
        {"surah": 2, "ayah": 1, "text_ar": "نص تجريبي", "text_en": "PLACEHOLDER verse about debt and provision."},
    ])
    db.insert_hadith(c, [
        _hadith("bukhari", "Sahih al-Bukhari", 1, "PLACEHOLDER hadith about patience in affliction."),
        _hadith("muslim", "Sahih Muslim", 5, "PLACEHOLDER introduction narration about patience.", book=0),
        _hadith("abudawud", "Sunan Abi Dawud", 10, "PLACEHOLDER sahih hadith about kinship ties.",
                [{"name": "Al-Albani", "grade": "Sahih"}]),
        _hadith("abudawud", "Sunan Abi Dawud", 11, "PLACEHOLDER weak hadith about patience.",
                [{"name": "Al-Albani", "grade": "Daif"}]),
        _hadith("tirmidhi", "Jami' at-Tirmidhi", 20, "PLACEHOLDER ungraded hadith about patience."),
    ])
    c.commit()
    yield c
    c.close()


@pytest.fixture
def settings():
    return Settings(db_path=Path(":memory:"), model="test-model", llm_enabled=False, max_verses=5, max_hadith=5)


@pytest.fixture
def make_client(conn, settings):
    def _make(llm=None):
        return TestClient(create_app(settings=settings, conn=conn, llm=llm))
    return _make
