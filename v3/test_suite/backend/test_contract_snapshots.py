import sys
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


def assert_message_meta(payload):
    assert isinstance(payload, dict)
    assert set(payload["message"].keys()) == {"message_id", "level", "user_text"}


class TestContractSnapshots:
    def test_runtime_health_snapshot_shape(self, client):
        resp = client.get("/health/runtime")
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        expected = {"status", "api", "ws", "kb_reindex_mode", "message"}
        assert set(body.keys()) == expected

    def test_login_snapshot_shape(self, client):
        resp = client.post("/login", json={"email": "student@example.com", "password": "student123"})
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        expected = {"access_token", "token_type", "role", "username", "email", "message"}
        assert set(body.keys()) == expected

    def test_auth_session_snapshot_shape(self, client):
        token = login(client)
        resp = client.get("/auth/session", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        expected = {"authenticated", "username", "email", "role", "message"}
        assert set(body.keys()) == expected

    def test_languages_snapshot_shape(self, client):
        token = login(client)
        resp = client.get("/languages", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {"languages", "message"}
        assert isinstance(body["languages"], list)

    def test_plan_limits_snapshot_shape(self, client):
        token = login(client)
        resp = client.get("/plan/limits", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        expected = {"plan_code", "effective_limits", "all_limits", "message"}
        assert set(body.keys()) == expected

    # ------------------------------------------------------------------
    # Phase 3: Commercial extraction seam snapshots
    # ------------------------------------------------------------------

    def test_plan_me_snapshot_shape(self, client):
        token = login(client)
        resp = client.get("/plan/me", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {"plan", "usage", "message"}
        assert set(body["plan"].keys()) == {
            "user_id",
            "plan_code",
            "plan_started_at",
            "plan_expires_at",
            "auto_renew",
            "is_trial",
            "trial_ends_at",
            "limits",
            "entitlements",
            "classes",
        }
        assert set(body["usage"].keys()) == {
            "uploads_count",
            "quiz_count",
            "flashcard_count",
            "lesson_count",
            "ask_count",
        }

    def test_subscription_catalog_snapshot_shape(self, client):
        token = login(client)
        resp = client.get("/subscription/catalog", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {"class_rates", "plans", "promo_codes_supported", "billing_period", "message"}
        assert isinstance(body["class_rates"], list)
        assert set(body["plans"].keys()) == {"free", "pro", "premium"}

    def test_subscription_quote_snapshot_shape(self, client):
        token = login(client)
        resp = client.post(
            "/subscription/quote",
            headers=auth_headers(token),
            json={"class_names": ["Class 8"], "promo_code": "WELCOME10", "auto_renew": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {
            "classes",
            "subtotal_cents",
            "discount_cents",
            "total_cents",
            "currency",
            "promo",
            "billing_period",
            "auto_renew",
            "message",
        }
        assert isinstance(body["classes"], list)
        assert isinstance(body["auto_renew"], bool)

    def test_subscription_activate_snapshot_shape(self, client):
        token = login(client)
        resp = client.post(
            "/subscription/activate",
            headers=auth_headers(token),
            json={
                "class_names": ["Class 8"],
                "promo_code": "WELCOME10",
                "auto_renew": True,
                "payment_reference": "snapshot-txn-123",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {
            "classes",
            "subtotal_cents",
            "discount_cents",
            "total_cents",
            "currency",
            "promo",
            "billing_period",
            "auto_renew",
            "activated_at",
            "expires_at",
            "active_classes",
            "payment_reference",
            "message",
        }
        assert isinstance(body["active_classes"], list)
        assert body["payment_reference"] == "snapshot-txn-123"

    def test_relationships_snapshot_shape(self, client):
        teacher_email = "snapshot_teacher@example.com"
        reg = client.post(
            "/register",
            json={
                "first_name": "Snapshot",
                "last_name": "Teacher",
                "email": teacher_email,
                "dob": "1990-01-01",
                "password": "pass1234",
                "role": "teacher",
            },
        )
        assert reg.status_code in (200, 409)

        token = login(client, teacher_email, "pass1234")
        resp = client.get("/relationships/my-students", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {"students", "message"}
        assert isinstance(body["students"], list)

    def test_lesson_sessions_snapshot_shape(self, client):
        token = login(client)
        resp = client.get("/lesson-plan/sessions", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {"sessions", "message"}
        assert isinstance(body["sessions"], list)

    def test_quiz_sessions_snapshot_shape(self, client):
        token = login(client)
        resp = client.get("/quiz/sessions", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {"sessions", "message"}
        assert isinstance(body["sessions"], list)

    def test_flashcard_sessions_snapshot_shape(self, client):
        token = login(client)
        resp = client.get("/flashcards/sessions", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {"sessions", "message"}
        assert isinstance(body["sessions"], list)

    def test_upload_tree_snapshot_shape(self, client):
        token = login(client)
        resp = client.get("/files/tree", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {"items", "message"}
        assert isinstance(body["items"], list)

    def test_upload_index_status_snapshot_shape(self, client):
        token = login(client)
        resp = client.get("/files/index-status", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {"items", "message"}
        assert isinstance(body["items"], list)

    def test_ask_success_snapshot_shape(self, client):
        token = login(client)
        with (
            patch("app.api.routes._consume_quota_or_raise", return_value=None),
            patch("app.api.routes.generate_answer", return_value="Snapshot answer")
        ):
            resp = client.post(
                "/ask",
                headers=auth_headers(token),
                json={"query": "Explain photosynthesis in one line."},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        expected = {"answer", "session_id", "model_used", "message"}
        assert set(body.keys()) == expected
        assert isinstance(body["answer"], str)
        assert isinstance(body["session_id"], str)

    def test_ask_validation_error_snapshot_shape(self, client):
        token = login(client)
        resp = client.post(
            "/ask",
            headers=auth_headers(token),
            json={"query": ""},
        )

        assert resp.status_code == 422
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {"message", "error"}

    # ------------------------------------------------------------------
    # Phase 1: Analytics + Progress extraction seam snapshots
    # ------------------------------------------------------------------

    def test_progress_dashboard_snapshot_shape(self, client):
        token = login(client)
        resp = client.get("/progress/dashboard", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        expected_keys = {
            "total_study_seconds",
            "streak_days",
            "totals",
            "top_subjects",
            "recent_activity",
            "mastery_summary",
            "assessment_summary",
            "assignments",
            "message",
        }
        assert set(body.keys()) == expected_keys
        assert isinstance(body["total_study_seconds"], int)
        assert isinstance(body["streak_days"], int)
        assert isinstance(body["totals"], dict)
        assert set(body["totals"].keys()) == {"quizzes", "lessons", "assessments"}
        assert isinstance(body["top_subjects"], list)
        assert isinstance(body["recent_activity"], list)
        assert isinstance(body["mastery_summary"], list)
        assert isinstance(body["assessment_summary"], dict)

    def test_progress_mastery_snapshot_shape(self, client):
        token = login(client)
        resp = client.get("/progress/mastery", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {"mastery", "message"}
        assert isinstance(body["mastery"], list)

    def test_progress_insights_snapshot_shape(self, client):
        token = login(client)
        resp = client.get("/progress/insights", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {"headline", "recommendations", "badges", "notifications", "message"}
        assert isinstance(body["headline"], str)
        assert isinstance(body["recommendations"], list)
        assert isinstance(body["badges"], list)
        assert isinstance(body["notifications"], list)

    def test_progress_study_plan_snapshot_shape(self, client):
        token = login(client)
        resp = client.get("/progress/study-plan", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {"headline", "focus_subject", "schedule", "goal_summary", "targets", "history", "message"}
        assert isinstance(body["headline"], str)
        assert isinstance(body["focus_subject"], str)
        assert isinstance(body["schedule"], list)
        assert isinstance(body["goal_summary"], dict)
        assert isinstance(body["targets"], list)
        assert isinstance(body["history"], dict)

    def test_progress_activity_snapshot_shape(self, client):
        token = login(client)
        resp = client.post(
            "/progress/activity",
            headers=auth_headers(token),
            json={"activity_type": "quiz", "subject": "Math", "chapter": "Algebra"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert_message_meta(body)
        assert set(body.keys()) == {"logged", "activity_id", "message"}
        assert body["logged"] is True
        assert isinstance(body["activity_id"], int)
