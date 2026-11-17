# QuranSolver

A web app that helps people reflect on their problems in the light of the
Qur'an and **authentic** hadith.

A user describes what they're going through. The app finds relevant verses
and hadith from a verified database and, when Claude is configured, writes
compassionate guidance that cites those texts. Scripture is **never generated
by the AI**: every verse and hadith shown comes from the database, and every
citation is checked before it's displayed.

## How it works

```
problem ──► safety check ──► search plan ──► retrieval ──► explanation ──► verification
            (crisis /        (Claude, or     (SQLite FTS5  (Claude cites   (unknown IDs and
             fiqh rules,      curated theme   over Qur'an + texts by ID      invented quotes are
             no LLM)          keywords)       authentic     only)            dropped; only cited
                                              hadith only)                   texts are shown)
```

| Module | Role |
|---|---|
| `quransolver/safety.py` | Deterministic checks that run first: crisis (self-harm, abuse) → help resources; fiqh-ruling questions → "consult a scholar" note |
| `quransolver/authenticity.py` | Hadith grading rules (see below) |
| `quransolver/themes.py` | Curated problem → search-term map (keywords only, no scripture) |
| `quransolver/search.py` | BM25 full-text search over English and normalized Arabic |
| `quransolver/llm.py` | Claude: search planning + explanation via structured outputs |
| `quransolver/solver.py` | The pipeline and citation verification |
| `quransolver/api.py` | FastAPI app + static web page |
| `scripts/import_data.py` | Downloads the corpus and builds `data/quransolver.db` |

### Two modes

- **Guided mode** (Claude API credentials set): Claude turns the problem into
  search terms, then writes guidance citing the retrieved texts by ID. Points
  citing anything that wasn't retrieved, or containing quotations that aren't
  in the cited text, are removed. Only cited texts are shown.
- **Search-only mode** (no credentials): curated theme keywords drive the
  search and results are labeled as keyword matches. If Claude is
  unavailable mid-request, guided mode falls back to this.

### Authenticity rules

Only Qur'an verses and hadith accepted as authentic are indexed, so nothing
else can come back from a search.

- **Sahih al-Bukhari, Sahih Muslim:** accepted, except Muslim's introduction
  (book 0).
- **Abu Dawud, Tirmidhi, Nasa'i, Ibn Majah:** accepted only when al-Albani's
  grade is a plain Sahih/Hasan grade. Chain-only grades ("Sahih Isnaad"),
  Companion/Successor statements (Mauquf/Maqtu), weak, rejected and
  fabricated narrations are excluded, as are narrations al-Albani didn't grade.

Current corpus: 6,236 verses; 29,765 of 34,085 hadith accepted.

## Running it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

python scripts/import_data.py          # ~15 s; downloads to data/raw/, builds data/quransolver.db

export ANTHROPIC_API_KEY=...           # optional: enables guided mode
uvicorn quransolver.api:app --reload   # open http://localhost:8000

pytest                                 # tests use a synthetic placeholder corpus
```

Configuration (environment variables):

| Variable | Default | Meaning |
|---|---|---|
| `QURANSOLVER_LLM` | `auto` | `on`, `off`, or `auto` (on when credentials exist) |
| `QURANSOLVER_MODEL` | `claude-opus-5-5` | Claude model for planning and explanation |
| `QURANSOLVER_DB` | `data/quransolver.db` | Database path |
| `QURANSOLVER_MAX_VERSES` / `_MAX_HADITH` | `8` / `8` | Texts retrieved per request |

### API

- `POST /api/ask` `{"problem": "..."}`: full pipeline
- `GET /api/search?q=patience&kind=quran|hadith`
- `GET /api/verse/{surah}/{ayah}`, `GET /api/hadith/{collection}/{number}`
- `GET /api/health`: mode, corpus counts, data sources

## Data sources and licensing

- Qur'an text and translations: [fawazahmed0/quran-api](https://github.com/fawazahmed0/quran-api)
  (Arabic text originally from Tanzil.net). Default translation: Abdullah Yusuf
  Ali. Choose another with `--translation`. **Check each translation's
  licence before publishing.** Several modern translations restrict redistribution.
- Hadith text and grades: [fawazahmed0/hadith-api](https://github.com/fawazahmed0/hadith-api).
  Check the terms for the English translations before a public launch.

## Before launch

- [ ] Have a qualified scholar review `authenticity.py`, `themes.py`, the
      prompts in `llm.py`, and a sample of outputs.
- [ ] Confirm translation licences.
- [ ] Localize crisis resources for your target countries.
- [ ] Add a "report a problem" button and log flagged answers for review.
- [ ] Add rate limiting and abuse protection on `/api/ask`.

## Roadmap

- **v1:** semantic (embedding) search so meaning, not just keywords, drives
  retrieval (keyword mode can still surface out-of-context verses); tafsir
  (Ibn Kathir, as-Sa'di) passed to Claude so verses are explained in context;
  links to sunnah.com for hadith; an evaluation set of real problems.
- **v2:** more languages, saved reflections, mobile app, scholar review dashboard.
