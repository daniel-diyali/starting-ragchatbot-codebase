"""API endpoint tests for the FastAPI app (backend/app.py).

These exercise the HTTP layer only: request validation, response shape,
status codes, and error propagation. The RAGSystem underneath is mocked
(see conftest.py's `mock_rag_system` / `client` fixtures), so these tests
don't touch ChromaDB, the embedding model, or the Anthropic API.
"""

import pytest


pytestmark = pytest.mark.api


class TestQueryEndpoint:
    def test_query_with_existing_session_returns_answer_and_sources(self, client, mock_rag_system):
        response = client.post(
            "/api/query",
            json={"query": "What is lesson 1 about?", "session_id": "existing-session"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == "This is a test answer."
        assert body["session_id"] == "existing-session"
        assert body["sources"] == [
            {"text": "Test Course - Lesson 1", "link": "https://example.com/course/lesson1"},
            {"text": "Test Course - Lesson 2", "link": None},
        ]

        # Provided a session_id, so a new one must not have been created.
        mock_rag_system.session_manager.create_session.assert_not_called()
        mock_rag_system.query.assert_called_once_with(
            "What is lesson 1 about?", "existing-session"
        )

    def test_query_without_session_id_creates_one(self, client, mock_rag_system):
        response = client.post("/api/query", json={"query": "What is lesson 1 about?"})

        assert response.status_code == 200
        body = response.json()
        assert body["session_id"] == "test-session-1"

        mock_rag_system.session_manager.create_session.assert_called_once()
        mock_rag_system.query.assert_called_once_with(
            "What is lesson 1 about?", "test-session-1"
        )

    def test_query_missing_query_field_is_422(self, client):
        response = client.post("/api/query", json={"session_id": "s1"})

        assert response.status_code == 422

    def test_query_empty_body_is_422(self, client):
        response = client.post("/api/query", json={})

        assert response.status_code == 422

    def test_query_propagates_rag_system_error_as_500(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("vector store unavailable")

        response = client.post("/api/query", json={"query": "boom", "session_id": "s1"})

        assert response.status_code == 500
        assert response.json()["detail"] == "vector store unavailable"

    def test_query_response_has_no_extra_fields(self, client):
        response = client.post("/api/query", json={"query": "hi", "session_id": "s1"})

        assert set(response.json().keys()) == {"answer", "sources", "session_id"}


class TestCoursesEndpoint:
    def test_get_course_stats_returns_analytics(self, client, mock_rag_system):
        response = client.get("/api/courses")

        assert response.status_code == 200
        assert response.json() == {
            "total_courses": 2,
            "course_titles": ["Test Course", "Another Course"],
        }
        mock_rag_system.get_course_analytics.assert_called_once()

    def test_get_course_stats_propagates_error_as_500(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("chroma is down")

        response = client.get("/api/courses")

        assert response.status_code == 500
        assert response.json()["detail"] == "chroma is down"

    def test_get_course_stats_missing_key_is_500(self, client, mock_rag_system):
        # A malformed analytics payload should surface as a 500, not a
        # raw KeyError bubbling up as an unhandled 500 with no detail.
        mock_rag_system.get_course_analytics.return_value = {"total_courses": 1}

        response = client.get("/api/courses")

        assert response.status_code == 500


class TestDeleteSessionEndpoint:
    def test_delete_session_success(self, client, mock_rag_system):
        response = client.delete("/api/session/some-session-id")

        assert response.status_code == 200
        assert response.json() == {"success": True}
        mock_rag_system.session_manager.delete_session.assert_called_once_with(
            "some-session-id"
        )

    def test_delete_session_propagates_error_as_500(self, client, mock_rag_system):
        mock_rag_system.session_manager.delete_session.side_effect = RuntimeError("no such session")

        response = client.delete("/api/session/missing")

        assert response.status_code == 500
        assert response.json()["detail"] == "no such session"


class TestStaticRoot:
    def test_root_serves_index_html(self, client):
        response = client.get("/")

        assert response.status_code == 200
        assert "Test Frontend" in response.text

    def test_unknown_path_is_404(self, client):
        # StaticFiles(html=True) only serves index.html for "/" and
        # directory URLs (or a 404.html, which we don't provide) - it is
        # not a catch-all SPA fallback for arbitrary unmatched paths.
        response = client.get("/some/unknown/route")

        assert response.status_code == 404
