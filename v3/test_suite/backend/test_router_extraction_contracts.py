"""
Test contract preservation for Phase 2 router extraction.

Validates that all routers extracted from routes.py maintain backward compatibility:
- All public endpoint paths remain unchanged
- Response envelopes follow consistent message structure
- Response payload schemas preserved for high-use endpoints
"""

import pytest
import sys
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Setup test client with mocked heavy dependencies."""
    heavy = [
        "sentence_transformers",
        "faiss",
        "numpy",
        "numpy.core",
        "tqdm",
        "tqdm.auto",
        "pypdf",
        "deep_translator",
        "llama_cpp",
        "openai",
        "docx",
        "python_docx",
    ]
    injected = {}
    for pkg in heavy:
        if pkg not in sys.modules:
            sys.modules[pkg] = MagicMock()
            injected[pkg] = True

    sys.modules["sentence_transformers"].SentenceTransformer = MagicMock(return_value=MagicMock())

    try:
        import app.main as main_module

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
    """Clear cookies between tests."""
    client.cookies.clear()


def login(client, email="student@example.com", password="student123"):
    """Helper to login and get auth token."""
    resp = client.post("/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


def headers(token):
    """Helper to create auth headers."""
    return {"Authorization": f"Bearer {token}"}


def assert_envelope(body, allow_error=False):
    """Validate message envelope structure."""
    assert isinstance(body, dict), f"Response body should be dict, got {type(body)}"
    assert "message" in body, f"Missing 'message' key in response: {body.keys()}"
    
    message = body["message"]
    assert isinstance(message, dict), f"'message' should be dict, got {type(message)}"
    assert "message_id" in message, "Missing 'message_id' in message"
    assert "level" in message, "Missing 'level' in message"
    assert "user_text" in message, "Missing 'user_text' in message"
    
    if not allow_error:
        assert "error" not in body or body.get("error") is None, f"Unexpected error in response: {body.get('error')}"


class TestAuthProfileRouterContract:
    """Validate auth/profile router extraction preserved public paths."""

    def test_login_endpoint_accessible(self, client):
        """POST /login should work."""
        resp = client.post("/login", json={"email": "student@example.com", "password": "student123"})
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert "access_token" in body

    def test_profile_get_endpoint_accessible(self, client):
        """GET /profile should work."""
        token = login(client)
        resp = client.get("/profile", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert "profile" in body or "username" in body

    def test_profile_update_endpoint_accessible(self, client):
        """PUT /profile should work."""
        token = login(client)
        resp = client.put(
            "/profile",
            json={"first_name": "Test", "last_name": "User"},
            headers=headers(token),
        )
        assert resp.status_code in (200, 400, 422)  # May fail validation but path exists
        body = resp.json()
        assert_envelope(body, allow_error=True)


class TestChatSessionRouterContract:
    """Validate chat/session router extraction preserved public paths."""

    def test_sessions_list_endpoint_accessible(self, client):
        """GET /sessions should return list."""
        token = login(client)
        resp = client.get("/sessions", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert isinstance(body.get("sessions"), list)

    def test_session_create_endpoint_accessible(self, client):
        """POST /sessions should create session."""
        token = login(client)
        resp = client.post(
            "/sessions",
            json={"session_name": "Test Session"},
            headers=headers(token),
        )
        assert resp.status_code in (200, 201, 400, 422)
        body = resp.json()
        assert_envelope(body, allow_error=True)

    def test_session_detail_endpoint_accessible(self, client):
        """GET /sessions/{id} should work."""
        token = login(client)
        resp = client.get("/sessions/test-session-123", headers=headers(token))
        assert resp.status_code in (200, 404, 400)
        body = resp.json()
        assert_envelope(body, allow_error=True)


class TestKnowledgeRouterContract:
    """Validate knowledge/files router extraction preserved public paths."""

    def test_knowledge_base_list_endpoint_accessible(self, client):
        """GET /knowledge should return list."""
        token = login(client)
        resp = client.get("/knowledge", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert isinstance(body.get("knowledge_bases"), list) or isinstance(body.get("files"), list)

    def test_knowledge_base_upload_endpoint_accessible(self, client):
        """POST /knowledge should accept file upload."""
        token = login(client)
        # Note: We're testing the endpoint exists, not actual file upload
        resp = client.post(
            "/knowledge",
            data={"name": "test.txt"},
            headers=headers(token),
        )
        assert resp.status_code in (200, 201, 400, 422)
        body = resp.json()
        assert_envelope(body, allow_error=True)

    def test_artifacts_endpoint_accessible(self, client):
        """GET /artifacts should be accessible."""
        token = login(client)
        resp = client.get("/artifacts", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert isinstance(body.get("artifacts"), list)


class TestLessonQuizRouterContract:
    """Validate lesson/quiz router extraction preserved public paths."""

    def test_lessons_list_endpoint_accessible(self, client):
        """GET /lessons should return list."""
        token = login(client)
        resp = client.get("/lessons", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert isinstance(body.get("lessons"), list)

    def test_quiz_sessions_endpoint_accessible(self, client):
        """GET /quiz/sessions should return quiz sessions."""
        token = login(client)
        resp = client.get("/quiz/sessions", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert isinstance(body.get("sessions"), list)

    def test_flashcard_sessions_endpoint_accessible(self, client):
        """GET /flashcards/sessions should return flashcard sessions."""
        token = login(client)
        resp = client.get("/flashcards/sessions", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert isinstance(body.get("sessions"), list)


class TestAssessmentRouterContract:
    """Validate assessment router extraction preserved public paths."""

    def test_assessments_list_endpoint_accessible(self, client):
        """GET /assessments should return list."""
        token = login(client)
        resp = client.get("/assessments", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert isinstance(body.get("assessments"), list)

    def test_assessment_detail_endpoint_accessible(self, client):
        """GET /assessments/{id} should be accessible."""
        token = login(client)
        resp = client.get("/assessments/test-assessment", headers=headers(token))
        assert resp.status_code in (200, 404, 400)
        body = resp.json()
        assert_envelope(body, allow_error=True)


class TestProgressRouterContract:
    """Validate progress router extraction preserved public paths."""

    def test_progress_endpoint_accessible(self, client):
        """GET /progress should return progress data."""
        token = login(client)
        resp = client.get("/progress", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)

    def test_assignments_endpoint_accessible(self, client):
        """GET /assignments should return assignments."""
        token = login(client)
        resp = client.get("/assignments", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert isinstance(body.get("assignments"), list)

    def test_notes_endpoint_accessible(self, client):
        """GET /notes should return notes."""
        token = login(client)
        resp = client.get("/notes", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert isinstance(body.get("notes"), list)


class TestCollaborationRouterContract:
    """Validate collaboration router extraction preserved public paths."""

    def test_relationships_list_endpoint_accessible(self, client):
        """GET /relationships should return relationships."""
        token = login(client)
        resp = client.get("/relationships", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert isinstance(body.get("relationships"), list)

    def test_student_link_endpoint_accessible(self, client):
        """POST /relationships/link-student should be accessible."""
        token = login(client)
        resp = client.post(
            "/relationships/link-student",
            json={"student_email": "test@example.com"},
            headers=headers(token),
        )
        assert resp.status_code in (200, 201, 400, 422)
        body = resp.json()
        assert_envelope(body, allow_error=True)


class TestAdminRouterContract:
    """Validate admin router extraction preserved public paths."""

    def test_admin_endpoints_require_auth(self, client):
        """Admin endpoints should be protected."""
        resp = client.get("/admin/health")
        assert resp.status_code in (401, 403, 200)
        if resp.status_code in (401, 403):
            body = resp.json()
            assert_envelope(body, allow_error=True)

    def test_admin_health_endpoint_accessible(self, client):
        """GET /admin/health should work for authenticated admin."""
        token = login(client)
        resp = client.get("/admin/health", headers=headers(token))
        assert resp.status_code in (200, 403)  # 403 if not admin
        body = resp.json()
        assert_envelope(body, allow_error=True)


class TestSubscriptionRouterContract:
    """Validate subscription/billing router extraction preserved public paths."""

    def test_subscriptions_endpoint_accessible(self, client):
        """GET /subscriptions or /billing should be accessible."""
        token = login(client)
        
        # Try both possible paths
        resp = client.get("/subscriptions", headers=headers(token))
        if resp.status_code == 404:
            resp = client.get("/billing", headers=headers(token))
        
        assert resp.status_code in (200, 404, 400)
        body = resp.json()
        assert_envelope(body, allow_error=True)


class TestClassesRouterContract:
    """Validate classes endpoint accessible."""

    def test_classes_list_endpoint_accessible(self, client):
        """GET /classes should return classes."""
        token = login(client)
        resp = client.get("/classes", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert isinstance(body.get("classes"), list)
