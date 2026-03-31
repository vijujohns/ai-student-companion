import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    import sys

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
    client.cookies.clear()


def login(client, email="student@example.com", password="student123"):
    resp = client.post("/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    body = resp.json()
    assert "message" in body
    return body["access_token"]


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def assert_envelope(body):
    assert isinstance(body, dict)
    assert "message" in body
    message = body["message"]
    assert isinstance(message, dict)
    assert "message_id" in message
    assert "level" in message
    assert "user_text" in message


class TestSuccessEnvelope:
    def test_sessions_success_enveloped(self, client):
        token = login(client)
        resp = client.get("/sessions", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert isinstance(body.get("sessions"), list)

    def test_classes_success_enveloped(self, client):
        token = login(client)
        resp = client.get("/classes", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert isinstance(body.get("classes"), list)

    def test_quiz_sessions_success_enveloped(self, client):
        token = login(client)
        resp = client.get("/quiz/sessions", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert isinstance(body.get("sessions"), list)

    def test_flashcard_sessions_success_enveloped(self, client):
        token = login(client)
        resp = client.get("/flashcards/sessions", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert_envelope(body)
        assert isinstance(body.get("sessions"), list)


class TestErrorEnvelope:
    def test_unauthenticated_error_enveloped(self, client):
        resp = client.get("/sessions")
        assert resp.status_code in (401, 403)
        body = resp.json()
        assert_envelope(body)
        assert "error" in body

    def test_validation_error_enveloped(self, client):
        resp = client.post("/login", json={"email": "", "password": ""})
        assert resp.status_code == 422
        body = resp.json()
        assert_envelope(body)
        assert "error" in body

    def test_not_found_error_enveloped(self, client):
        token = login(client)
        resp = client.get("/artifacts/999999", headers=headers(token))
        assert resp.status_code == 404
        body = resp.json()
        assert_envelope(body)
        assert "error" in body
