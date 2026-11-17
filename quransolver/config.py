"""Runtime configuration, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    db_path: Path
    model: str
    llm_enabled: bool
    max_verses: int
    max_hadith: int


def get_settings() -> Settings:
    llm_flag = os.environ.get("QURANSOLVER_LLM", "auto").lower()
    has_credentials = bool(
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    )
    if llm_flag == "off":
        llm_enabled = False
    elif llm_flag == "on":
        llm_enabled = True
    else:
        llm_enabled = has_credentials

    return Settings(
        db_path=Path(os.environ.get("QURANSOLVER_DB", ROOT / "data" / "quransolver.db")),
        model=os.environ.get("QURANSOLVER_MODEL", "claude-opus-5-5"),
        llm_enabled=llm_enabled,
        max_verses=int(os.environ.get("QURANSOLVER_MAX_VERSES", "8")),
        max_hadith=int(os.environ.get("QURANSOLVER_MAX_HADITH", "8")),
    )
