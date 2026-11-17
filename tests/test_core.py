from __future__ import annotations

import pytest

from quransolver.arabic import normalize_arabic
from quransolver.authenticity import classify, grade_is_authentic
from quransolver.llm import Guidance, GuidancePoint, LLMError, SearchPlan
from quransolver.safety import check
from quransolver.search import build_match_query, search
from quransolver.solver import solve, verify_guidance


@pytest.mark.parametrize("grade,ok", [
    ("Sahih", True),
    ("Hasan", True),
    ("Hasan Sahih", True),
    ("Sahih Lighairihi", True),
    ("Daif", False),
    ("Daif Isnaad", False),
    ("Sahih Isnaad", False),      # only the chain is graded
    ("Sahih Muquf", False),       # a Companion's statement
    ("Sahih Maqtu", False),       # a Successor's statement
    ("Hasan Sahih Isnaad", False),
    ("Munkar", False),
    ("Mawdu", False),
    ("Shadh", False),
    ("", False),
    (None, False),
])
def test_grade_is_authentic(grade, ok):
    assert grade_is_authentic(grade) is ok


def test_classify_collections():
    assert classify("bukhari", 3, [])[2] is True
    assert classify("muslim", 1, [])[2] is True
    assert classify("muslim", 0, [])[2] is False  # introduction
    assert classify("abudawud", 1, [{"name": "Zubair Ali Zai", "grade": "Sahih"}])[2] is False  # no Albani grade
    assert classify("nasai", 1, [{"name": "Al-Albani", "grade": "Hasan"}]) == ("Hasan", "Al-Albani", True)


def test_normalize_arabic():
    assert normalize_arabic("الصَّبْرُ") == "الصبر"
    assert normalize_arabic("إِيمَان") == "ايمان"
    assert normalize_arabic("رَحْمَة") == "رحمه"


def test_build_match_query_is_safe():
    assert build_match_query(['patience" OR 1=1 --', "NEAR(x y)"]) == '"patience" OR "near"'
    assert build_match_query(["the and of"]) is None


def test_search_excludes_unauthentic_hadith(conn):
    ids = {d["id"] for d in search(conn, ["patience"], "hadith", 10)}
    assert ids == {"H:bukhari:1"}  # weak, ungraded and intro narrations never surface


def test_search_quran_and_arabic(conn):
    assert [d["id"] for d in search(conn, ["kinship"], "quran", 10)] == ["Q:1:2"]
    assert [d["id"] for d in search(conn, ["صبر", "الصبر"], "quran", 10)] == ["Q:1:1"]


@pytest.mark.parametrize("text,crisis,scholar", [
    ("I want to kill myself", True, False),
    ("My husband hits me every week", True, False),
    ("Is it haram to take a mortgage?", False, True),
    ("I feel sad about my exams", False, False),
])
def test_safety_check(text, crisis, scholar):
    r = check(text)
    assert r.crisis is crisis
    assert r.needs_scholar is scholar
    assert bool(r.resources) is crisis


def _source(doc_id, text):
    return {"id": doc_id, "text_en": text, "reference": doc_id}


def test_verify_guidance_drops_unknown_citations():
    sources = [_source("Q:1:1", "PLACEHOLDER verse about patience and trust in hardship.")]
    g = Guidance(
        summary="s",
        points=[
            GuidancePoint(heading="ok", explanation="Be patient.", citations=["Q:1:1"]),
            GuidancePoint(heading="invented", explanation="x", citations=["Q:99:99"]),
            GuidancePoint(heading="mixed", explanation="x", citations=["Q:1:1", "H:fake:1"]),
            GuidancePoint(heading="none", explanation="x", citations=[]),
        ],
        practical_steps=["pray"],
    )
    verified, dropped = verify_guidance(g, sources)
    assert [p["heading"] for p in verified["points"]] == ["ok"]
    assert dropped == 3


def test_verify_guidance_rejects_invented_quotes():
    sources = [_source("Q:1:1", "PLACEHOLDER verse about patience and trust in hardship.")]
    g = Guidance(
        summary="s",
        points=[
            GuidancePoint(heading="real", explanation='It speaks of "patience and trust in hardship" here.', citations=["Q:1:1"]),
            GuidancePoint(heading="fake", explanation='It says "whoever worries will be given a palace".', citations=["Q:1:1"]),
        ],
        practical_steps=[],
    )
    verified, dropped = verify_guidance(g, sources)
    assert [p["heading"] for p in verified["points"]] == ["real"]
    assert dropped == 1


class FakeLLM:
    def __init__(self, fail_explain=False):
        self.fail_explain = fail_explain
        self.seen_sources = None

    def plan(self, problem):
        return SearchPlan(themes=["Sabr"], english_terms=["patience", "kinship"], arabic_terms=[],
                          is_ruling_question=False, crisis=False)

    def explain(self, problem, sources):
        if self.fail_explain:
            raise LLMError("boom")
        self.seen_sources = [s["id"] for s in sources]
        return Guidance(
            summary="We hear you.",
            points=[
                GuidancePoint(heading="Patience", explanation="Hold on.", citations=["Q:1:1", "H:bukhari:1"]),
                GuidancePoint(heading="Made up", explanation="x", citations=["H:bukhari:999"]),
            ],
            practical_steps=["Pray on time"],
        )


def test_solve_guided(conn, settings):
    llm = FakeLLM()
    r = solve(conn, settings, "I struggle with my family", llm)
    assert r["mode"] == "guided"
    assert "Sabr" in r["themes"]
    assert [p["heading"] for p in r["guidance"]["points"]] == ["Patience"]
    assert any("removed" in n for n in r["notices"])
    # the LLM only ever sees authentic, retrieved texts
    assert "H:abudawud:11" not in llm.seen_sources
    # only cited texts are shown in guided mode
    assert [d["id"] for d in r["verses"]] == ["Q:1:1"]
    assert [d["id"] for d in r["hadith"]] == ["H:bukhari:1"]


class InventingLLM(FakeLLM):
    def explain(self, problem, sources):
        return Guidance(summary="s", practical_steps=[], points=[
            GuidancePoint(heading="x", explanation="x", citations=["Q:50:50"])])


def test_solve_with_no_verified_points_falls_back(conn, settings):
    r = solve(conn, settings, "I need patience and kinship", InventingLLM())
    assert r["mode"] == "search"
    assert r["guidance"] is None
    assert r["verses"]  # retrieved texts are still shown, as keyword matches


def test_solve_falls_back_when_llm_fails(conn, settings):
    r = solve(conn, settings, "I need patience", FakeLLM(fail_explain=True))
    assert r["mode"] == "search"
    assert r["guidance"] is None
    assert r["verses"]


def test_solve_without_llm(conn, settings):
    r = solve(conn, settings, "I am anxious and need patience", None)
    assert r["mode"] == "search"
    assert "Anxiety and worry" in r["themes"]
    assert {d["id"] for d in r["hadith"]} == {"H:bukhari:1"}
