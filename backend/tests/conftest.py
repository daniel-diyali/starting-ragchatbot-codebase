"""Shared pytest fixtures for the backend test suite.

Notable design decision: tests do NOT `import app` (backend/app.py). That
module, at import time, instantiates a real RAGSystem (loading the
sentence-transformers embedding model and opening ChromaDB) and mounts
StaticFiles against "../frontend" relative to the process's CWD. Neither
is desirable in a test process, and the static mount raises at import
time if that path doesn't resolve from wherever pytest happens to run.

Instead, `api_test_app` below rebuilds the three API routes inline, wired
to a mocked RAGSystem, plus a static mount pointed at a throwaway temp
directory so "/" can still be exercised. Keep this in sync with
backend/app.py if its route logic changes.
"""

import sys
from pathlib import Path
from typing import List, Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from pydantic import BaseModel

# Make backend/ modules (models.py, etc.) importable regardless of the
# `pythonpath` ini option, in case tests are ever invoked without pyproject.toml
# being picked up as rootdir.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models import Course, CourseChunk, Lesson  # noqa: E402


# ---------------------------------------------------------------------------
# Sample domain data
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_lesson() -> Lesson:
    return Lesson(
        lesson_number=1,
        title="Introduction",
        lesson_link="https://example.com/course/lesson1",
    )


@pytest.fixture
def sample_course(sample_lesson: Lesson) -> Course:
    return Course(
        title="Test Course",
        course_link="https://example.com/course",
        instructor="Jane Doe",
        lessons=[
            sample_lesson,
            Lesson(lesson_number=2, title="Deep Dive", lesson_link=None),
        ],
    )


@pytest.fixture
def sample_course_chunk() -> CourseChunk:
    return CourseChunk(
        content="This is a test chunk of course content about lesson 1.",
        course_title="Test Course",
        lesson_number=1,
        chunk_index=0,
    )


@pytest.fixture
def sample_sources() -> List[dict]:
    """Shape produced by CourseSearchTool._format_results / ToolManager.get_last_sources."""
    return [
        {"text": "Test Course - Lesson 1", "link": "https://example.com/course/lesson1"},
        {"text": "Test Course - Lesson 2", "link": None},
    ]


# ---------------------------------------------------------------------------
# Mocked backend components
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_vector_store():
    """A MagicMock standing in for VectorStore, with sane default returns."""
    store = MagicMock()
    store.get_course_count.return_value = 2
    store.get_existing_course_titles.return_value = ["Test Course", "Another Course"]
    store.get_lesson_link.return_value = "https://example.com/course/lesson1"
    store.get_course_link.return_value = "https://example.com/course"
    return store


@pytest.fixture
def mock_ai_generator():
    """A MagicMock standing in for AIGenerator."""
    generator = MagicMock()
    generator.generate_response.return_value = "This is a test answer."
    return generator


@pytest.fixture
def mock_rag_system(sample_sources):
    """A MagicMock standing in for RAGSystem, wired for the API test app.

    `.session_manager` is itself a MagicMock so `create_session` /
    `delete_session` calls can be asserted on independently of `.query`.
    """
    rag = MagicMock()
    rag.session_manager.create_session.return_value = "test-session-1"
    rag.query.return_value = ("This is a test answer.", sample_sources)
    rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Test Course", "Another Course"],
    }
    return rag


# ---------------------------------------------------------------------------
# API test app (mirrors backend/app.py's routes without its side effects)
# ---------------------------------------------------------------------------


class _QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class _Source(BaseModel):
    text: str
    link: Optional[str] = None


class _QueryResponse(BaseModel):
    answer: str
    sources: List[_Source]
    session_id: str


class _CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


def build_api_test_app(rag_system, static_dir: Path) -> FastAPI:
    """Build a FastAPI app exposing the same routes as backend/app.py,
    backed by the given (mocked) rag_system, without the real startup
    ingestion hook or a mount pointed at the real frontend/ directory.
    """
    app = FastAPI(title="Course Materials RAG System (test)")

    @app.post("/api/query", response_model=_QueryResponse)
    async def query_documents(request: _QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = rag_system.session_manager.create_session()

            answer, sources = rag_system.query(request.query, session_id)

            return _QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/session/{session_id}")
    async def delete_session(session_id: str):
        try:
            rag_system.session_manager.delete_session(session_id)
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=_CourseStats)
    async def get_course_stats():
        try:
            analytics = rag_system.get_course_analytics()
            return _CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Mirrors app.py's `app.mount("/", StaticFiles(directory="../frontend", ...))`
    # but against a throwaway directory so "/" is exercisable without the
    # real frontend/ folder being present or discoverable from CWD.
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text("<html><body>Test Frontend</body></html>")
    return tmp_path


@pytest.fixture
def api_test_app(mock_rag_system, static_dir) -> FastAPI:
    return build_api_test_app(mock_rag_system, static_dir)


@pytest.fixture
def client(api_test_app) -> TestClient:
    return TestClient(api_test_app)
