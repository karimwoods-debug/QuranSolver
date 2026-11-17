"""FastAPI application: JSON API + the static web page."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db
from .config import Settings, get_settings
from .llm import LLM, ClaudeLLM
from .search import search
from .solver import solve

log = logging.getLogger(__name__)
STATIC = Path(__file__).resolve().parent / "static"


class AskRequest(BaseModel):
    problem: str = Field(min_length=3, max_length=2000)


def create_app(
    settings: Settings | None = None,
    conn: sqlite3.Connection | None = None,
    llm: LLM | None = None,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if conn is not None:
            app.state.conn = conn
        else:
            if not settings.db_path.exists():
                raise RuntimeError(
                    f"Database not found at {settings.db_path}. Run: python scripts/import_data.py"
                )
            app.state.conn = db.connect(settings.db_path)
        if llm is not None:
            app.state.llm = llm
        elif settings.llm_enabled:
            app.state.llm = ClaudeLLM(settings.model)
        else:
            app.state.llm = None
        yield

    app = FastAPI(title="QuranSolver", version="0.1.0", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.get("/api/health")
    def health(request: Request) -> dict[str, Any]:
        c = request.app.state.conn
        return {
            "status": "ok",
            "guided_mode": request.app.state.llm is not None,
            "counts": db.counts(c),
            "sources": db.get_meta(c),
        }

    @app.post("/api/ask")
    def ask(body: AskRequest, request: Request) -> dict[str, Any]:
        return solve(request.app.state.conn, settings, body.problem, request.app.state.llm)

    @app.get("/api/search")
    def search_endpoint(
        request: Request,
        q: str = Query(min_length=2, max_length=200),
        kind: str = Query("quran", pattern="^(quran|hadith)$"),
        limit: int = Query(10, ge=1, le=50),
    ) -> dict[str, Any]:
        return {"results": search(request.app.state.conn, q.split(), kind, limit)}

    @app.get("/api/verse/{surah}/{ayah}")
    def verse(surah: int, ayah: int, request: Request) -> dict[str, Any]:
        doc = db.get_verse(request.app.state.conn, db.verse_id(surah, ayah))
        if doc is None:
            raise HTTPException(404, "Verse not found")
        return doc

    @app.get("/api/hadith/{collection}/{number}")
    def hadith(collection: str, number: int, request: Request) -> dict[str, Any]:
        doc = db.get_hadith(request.app.state.conn, db.hadith_id(collection, number))
        if doc is None:
            raise HTTPException(404, "Hadith not found or not graded authentic")
        return doc

    return app


app = create_app()
