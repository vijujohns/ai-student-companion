"""Learning Session extraction seam tests.

Verifies that session, lesson, quiz, and flashcard session routes delegate
through `services.learning` instead of directly wiring DB/module helpers.
"""

import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(scope="module")
def client():
    heavy = [
        "sentence_transformers", "faiss", "numpy", "numpy.core",
        "tqdm", "tqdm.auto", "pypdf", "deep_translator",
        "llama_cpp", "openai", "docx", "python_docx",
    ]
    injected = {}
    for pkg in heavy:
        if pkg not in sys.modules:
            sys.modules[pkg] = MagicMock()
            injected[pkg] = True

    sys.modules["sentence_transformers"].SentenceTransformer = MagicMock(return_value=MagicMock())

    try:
        import app.main as main_module
        from fastapi.testclient import TestClient

        with (
            patch.object(main_module, "load_index", return_value=None),
            patch.object(main_module, "load_knowledge_base", return_value=None),
            patch.object(main_module, "init_db", return_value=None),
            patch("threading.Thread"),
        ):
            from app.modules.db import init_db
            init_db()
            with TestClient(main_module.app, raise_server_exceptions=True) as c:
                yield c
    finally:
        for pkg in injected:
            del sys.modules[pkg]


@pytest.fixture(autouse=True)
def clear_client_cookies(client):
    client.cookies.clear()


def login(client, email="student@example.com", password="student123"):
    resp = client.post("/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def ensure_existing_session_id() -> str:
    from app.modules.db import get_connection

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT session_id FROM chat_history WHERE user_id=? ORDER BY id DESC LIMIT 1",
            ("student",),
        )
        row = cur.fetchone()
        if row and row[0]:
            return row[0]

        session_id = f"seam-session-{uuid.uuid4().hex}"
        cur.execute(
            """
            INSERT INTO chat_history (user_id, session_id, user_message, ai_response, session_title)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("student", session_id, "hello", "hi", "Seam Session"),
        )
        conn.commit()
        return session_id
    finally:
        conn.close()


class TestLearningSessionRouteSeam:
    def test_sessions_route_uses_learning_service_registry(self, client):
        token = login(client)
        stub = [{"id": "s1", "title": "Chat A", "last_updated": "2026-01-01", "selected_content": None}]
        with patch("app.api.routes.services") as mock_services:
            mock_services.learning.list_chat_sessions.return_value = stub
            resp = client.get("/sessions", headers=auth_headers(token))

        assert resp.status_code == 200
        assert resp.json()["sessions"] == stub
        mock_services.learning.list_chat_sessions.assert_called_once_with("student")

    def test_rename_session_route_uses_learning_service_registry(self, client):
        token = login(client)
        session_id = ensure_existing_session_id()
        with patch("app.api.routes.services") as mock_services:
            mock_services.learning.rename_chat_session.return_value = {"status": "updated"}
            resp = client.put(f"/sessions/{session_id}", headers=auth_headers(token), json={"title": "Renamed"})

        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"
        mock_services.learning.rename_chat_session.assert_called_once_with("student", session_id, "Renamed")

    def test_delete_session_route_uses_learning_service_registry(self, client):
        token = login(client)
        session_id = ensure_existing_session_id()
        with patch("app.api.routes.services") as mock_services:
            mock_services.learning.delete_chat_session.return_value = {"status": "deleted"}
            resp = client.delete(f"/sessions/{session_id}", headers=auth_headers(token))

        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        mock_services.learning.delete_chat_session.assert_called_once_with("student", session_id)

    def test_get_session_content_route_uses_learning_service_registry(self, client):
        token = login(client)
        with patch("app.api.routes.services") as mock_services:
            mock_services.learning.get_session_content.return_value = {"session_content": "kb:abc123"}
            resp = client.get("/sessions/session-1/content", headers=auth_headers(token))

        assert resp.status_code == 200
        assert resp.json()["session_content"] == "kb:abc123"
        mock_services.learning.get_session_content.assert_called_once()

    def test_set_session_content_route_uses_learning_service_registry(self, client):
        token = login(client)
        with patch("app.api.routes.services") as mock_services:
            mock_services.learning.set_session_content.return_value = {"status": "updated", "session_content": "kb:xyz"}
            resp = client.put(
                "/sessions/session-1/content",
                headers=auth_headers(token),
                json={"content_id": "kb:xyz"},
            )

        assert resp.status_code == 200
        assert resp.json()["session_content"] == "kb:xyz"
        mock_services.learning.set_session_content.assert_called_once()

    def test_lesson_sessions_route_uses_learning_service_registry(self, client):
        token = login(client)
        stub = [{"session_id": "lesson-1", "title": "Lesson 1"}]
        with patch("app.api.routes.services") as mock_services:
            mock_services.learning.list_lesson_sessions.return_value = stub
            resp = client.get("/lesson-plan/sessions", headers=auth_headers(token))

        assert resp.status_code == 200
        assert resp.json()["sessions"] == stub
        mock_services.learning.list_lesson_sessions.assert_called_once_with("student")

    def test_quiz_sessions_route_uses_learning_service_registry(self, client):
        token = login(client)
        stub = [{"session_id": "quiz-1", "title": "Quiz 1"}]
        with patch("app.api.routes.services") as mock_services:
            mock_services.learning.list_quiz_sessions.return_value = stub
            resp = client.get("/quiz/sessions", headers=auth_headers(token))

        assert resp.status_code == 200
        assert resp.json()["sessions"] == stub
        mock_services.learning.list_quiz_sessions.assert_called_once_with("student")

    def test_flashcard_sessions_route_uses_learning_service_registry(self, client):
        token = login(client)
        stub = [{"session_id": "flash-1", "title": "Flash 1"}]
        with patch("app.api.routes.services") as mock_services:
            mock_services.learning.list_flashcard_sessions.return_value = stub
            resp = client.get("/flashcards/sessions", headers=auth_headers(token))

        assert resp.status_code == 200
        assert resp.json()["sessions"] == stub
        mock_services.learning.list_flashcard_sessions.assert_called_once_with("student")

    def test_latest_quiz_route_uses_learning_service_registry(self, client):
        token = login(client)
        stub = {"quiz_id": "q1", "questions": [{"question": "Q?"}]}
        with patch("app.api.routes.services") as mock_services:
            mock_services.learning.get_latest_quiz.return_value = stub
            resp = client.get("/quiz/latest", params={"session_id": "session-1"}, headers=auth_headers(token))

        assert resp.status_code == 200
        assert resp.json()["quiz_id"] == "q1"
        mock_services.learning.get_latest_quiz.assert_called_once_with("student", "session-1")

    def test_latest_flashcards_route_uses_learning_service_registry(self, client):
        token = login(client)
        stub = {"artifact_id": 7, "cards": [{"front": "A", "back": "B"}]}
        with patch("app.api.routes.services") as mock_services:
            mock_services.learning.get_latest_flashcards.return_value = stub
            resp = client.get("/flashcards/latest", params={"session_id": "session-1"}, headers=auth_headers(token))

        assert resp.status_code == 200
        assert resp.json()["artifact"] == stub
        mock_services.learning.get_latest_flashcards.assert_called_once_with("student", "session-1")
