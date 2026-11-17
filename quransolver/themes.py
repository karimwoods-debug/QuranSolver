"""Curated theme map used to widen searches (and the only query expansion
when the LLM is off).

This file holds keywords only, never scripture text, so it cannot misquote
anything. Search terms are chosen to match the wording of the English
translations in the corpus (e.g. "persevere", "kinship"). Have a scholar
review and extend it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    triggers: tuple[str, ...]
    terms: tuple[str, ...]


THEMES: tuple[Theme, ...] = (
    Theme(
        "Anxiety and worry",
        ("anxious", "anxiety", "worry", "worried", "stress", "stressed", "afraid",
         "fear", "overwhelmed", "panic", "nervous", "future"),
        ("patience", "persevere", "trust", "hearts", "rest", "remembrance",
         "ease", "hardship", "burden", "fear", "grieve"),
    ),
    Theme(
        "Grief and loss",
        ("died", "death", "grief", "grieving", "loss", "lost", "mourning",
         "passed away", "funeral", "miscarriage"),
        ("patience", "calamity", "affliction", "return", "reward", "grieve",
         "death", "persevere"),
    ),
    Theme(
        "Sadness and hopelessness",
        ("sad", "sadness", "depressed", "depression", "hopeless", "despair",
         "lonely", "loneliness", "empty", "down"),
        ("despair", "mercy", "hardship", "ease", "grieve", "near", "call",
         "hope", "sorrow"),
    ),
    Theme(
        "Family and ties of kinship",
        ("parents", "mother", "father", "mom", "dad", "sibling", "brother",
         "sister", "family", "relatives", "cousin", "uncle", "aunt", "children"),
        ("parents", "kindness", "kinship", "ties", "relatives", "kin",
         "womb", "forgive", "dutiful"),
    ),
    Theme(
        "Marriage and spouses",
        ("marriage", "married", "spouse", "wife", "husband", "divorce",
         "engaged", "fiance"),
        ("spouses", "wives", "husband", "tranquillity", "love", "mercy",
         "kindness", "kindly"),
    ),
    Theme(
        "Anger and conflict",
        ("angry", "anger", "rage", "temper", "fight", "argument", "argue",
         "conflict", "hate", "resent"),
        ("anger", "angry", "restrain", "forgive", "pardon", "strong",
         "reconcile"),
    ),
    Theme(
        "Money, debt and provision",
        ("debt", "money", "poor", "poverty", "job", "unemployed", "work",
         "rizq", "provision", "financial", "bills", "loan", "business"),
        ("provision", "sustenance", "debt", "poverty", "wealth", "trust",
         "charity", "earn", "lawful"),
    ),
    Theme(
        "Sin, guilt and repentance",
        ("sin", "sinned", "guilt", "guilty", "regret", "repent", "ashamed",
         "shame", "relapse", "addiction", "mistake"),
        ("repent", "repentance", "forgive", "forgiveness", "mercy", "despair",
         "sins", "turn"),
    ),
    Theme(
        "Illness and hardship",
        ("sick", "illness", "ill", "disease", "pain", "hospital", "cancer",
         "injury", "disability", "chronic"),
        ("sickness", "illness", "affliction", "patience", "cure", "heal",
         "hardship", "sins"),
    ),
    Theme(
        "Envy and jealousy",
        ("jealous", "jealousy", "envy", "envious", "compare", "comparing"),
        ("envy", "envies", "jealousy", "hatred", "brother", "contentment"),
    ),
    Theme(
        "Decisions and guidance",
        ("decision", "decide", "choose", "choice", "confused", "uncertain",
         "unsure", "lost"),
        ("consult", "consultation", "trust", "guidance", "guide", "istikhara",
         "resolve"),
    ),
    Theme(
        "Faith and motivation",
        ("faith", "iman", "weak", "motivation", "prayer", "pray", "salah",
         "lazy", "doubt"),
        ("faith", "prayer", "remembrance", "hearts", "believers", "guidance",
         "steadfast"),
    ),
)


def match_themes(text: str) -> list[Theme]:
    lowered = text.lower()
    found: list[Theme] = []
    for theme in THEMES:
        for trig in theme.triggers:
            if re.search(rf"\b{re.escape(trig)}\b", lowered):
                found.append(theme)
                break
    return found
