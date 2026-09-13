# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Course Materials RAG System — a FastAPI backend + vanilla-JS frontend that answers questions about course transcripts using ChromaDB vector search and Anthropic Claude with tool calling.

## Commands

```bash
uv sync                                             # install deps (Python >=3.13)
./run.sh                                            # start the app (http://localhost:8000)
cd backend && uv run uvicorn app:app --reload --port 8000   # equivalent manual start
uv add <package>                                    # add a dependency (edit pyproject.toml via uv, not by hand)
uv run <script>.py                                  # run any Python file
./scripts/format.sh                                 # black + ruff --fix (mutates files)
./scripts/lint.sh                                   # ruff check only, no mutation
./scripts/check.sh                                  # black --check + ruff check; CI-style quality gate
```

**Always use `uv`.** Run every Python file and module through `uv run` (`uv run script.py`, `uv run python -m module`) — never bare `python`. Never call `pip` directly; use `uv sync` / `uv add` so `uv.lock` and the managed venv stay in sync.

Requires `ANTHROPIC_API_KEY` in a root `.env` (see `.env.example`). API docs at `/docs`.

There is no test suite configured. `main.py` at the repo root is an unused scaffold stub — the real entrypoint is `backend/app.py`.

### Code quality

Black (formatting) and ruff (linting + import sorting) are dev dependencies, configured in `[tool.black]` / `[tool.ruff]` in `pyproject.toml` (both at `line-length = 100`; ruff's `E501` is disabled since black owns line length). `scripts/format.sh` applies both; `scripts/check.sh` verifies without mutating and is the one to wire into CI or a pre-commit hook. `backend/app.py` carries a `per-file-ignores` entry for `E402` because `warnings.filterwarnings()` intentionally runs before the fastapi/chromadb import chain.

**The server must be started from `backend/`.** Several paths are CWD-relative: `../docs` (startup ingestion), `../frontend` (static mount), and `CHROMA_PATH = "./chroma_db"` → `backend/chroma_db/`. Running uvicorn from the repo root silently creates a second, empty Chroma store and 404s the frontend.

## Architecture

Request flow: `frontend/script.js` → `POST /api/query` (`backend/app.py`) → `RAGSystem.query` → `AIGenerator` → Claude → (optional tool call) → `CourseSearchTool` → `VectorStore` → ChromaDB.

### Search is agentic, not a retrieve-then-generate pipeline

`RAGSystem.query` does **not** search. It hands Claude a `search_course_content` tool definition and lets the model decide whether to call it. Consequences worth knowing before changing retrieval:

- `AIGenerator._handle_tool_execution` supports exactly **one** tool round-trip — the follow-up API call omits `tools`, so Claude cannot search again. The system prompt in `ai_generator.py` also states "one search per query maximum". Multi-step search requires changing both.
- Sources reach the UI **out of band**, not through the model's text: `CourseSearchTool.execute` stashes `last_sources`, `ToolManager.get_last_sources()` scrapes it after generation, and `RAGSystem` resets it per query. `get_last_sources()` returns the first tool with a non-empty `last_sources`, so a second source-tracking tool would need that logic reworked.
- New tools: subclass `Tool` in `search_tools.py` and register in `RAGSystem.__init__`.

### Two ChromaDB collections, course title as primary key

`vector_store.py` maintains `course_catalog` (one embedded document per course title; metadata holds instructor, links, and lessons serialized into a `lessons_json` string because Chroma metadata must be scalar) and `course_content` (the chunks). A fuzzy `course_name` from the model is resolved to a canonical title by vector-searching `course_catalog` first (`_resolve_course_name`), then used as an exact `where` filter on `course_content`. The course title string is the Chroma ID in the catalog and the join key in chunk metadata — renaming a course title in a doc creates a new course.

### Ingestion and its staleness trap

On startup `app.py` calls `add_course_folder("../docs", clear_existing=False)`, which **skips any file whose parsed course title already exists** in the catalog. Editing an existing transcript therefore has no effect on the index. To re-index: delete `backend/chroma_db/`, or call `add_course_folder(..., clear_existing=True)`.

`document_processor.py` expects a specific transcript format (see `docs/*.txt`):

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <lesson title>
Lesson Link: <url>
<lesson body...>
```

Metadata is parsed from the first ~4 lines; `Lesson N:` markers split the body. Text is chunked on sentence boundaries up to `CHUNK_SIZE` chars with `CHUNK_OVERLAP` chars of sentence-level overlap, and chunks are prefixed with course/lesson context before embedding so the text itself carries provenance. Files with no `Lesson N:` marker fall back to one unlabeled chunk set.

### Sessions

`session_manager.py` is in-memory only — a plain dict, sequential `session_N` IDs from a counter, truncated to `MAX_HISTORY * 2` messages. Everything resets on restart, and IDs collide across restarts. History is injected into the Claude call as a formatted string appended to the system prompt, not as real message turns.

### Tunables

All in `backend/config.py` (`chunk` sizes, `MAX_RESULTS`, `MAX_HISTORY`, `EMBEDDING_MODEL`, `ANTHROPIC_MODEL`). The model is pinned there, not in `.env`.
