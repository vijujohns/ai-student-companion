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

    st_mock = sys.modules["sentence_transformers"]
    st_mock.SentenceTransformer = MagicMock(return_value=MagicMock())

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
def clear_cookies(client):
    client.cookies.clear()


def _login(client, email="student@example.com", password="student123"):
    resp = client.post("/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str):
    return {"Authorization": f"Bearer {token}"}


class TestSummaryNotesApi:
    def test_student_can_create_list_update_and_delete_notes(self, client):
        token = _login(client)

        create_resp = client.post(
            "/notes/save",
            headers=_auth(token),
            json={
                "title": "Refraction Revision Notes",
                "content": "## 📘 Refraction\n\n### Overview\nLight bends when it moves between media.",
                "session_id": "summary-session-1",
                "source_query": "Summarize refraction for revision notes",
                "selected_content": "upload:42",
            },
        )
        assert create_resp.status_code == 200, create_resp.text
        created = create_resp.json()
        assert created["status"] == "saved"
        assert created["note"]["title"] == "Refraction Revision Notes"
        note_id = created["note"]["id"]

        list_resp = client.get("/notes", headers=_auth(token))
        assert list_resp.status_code == 200, list_resp.text
        notes = list_resp.json()["notes"]
        assert any(item["id"] == note_id and item["source_query"] == "Summarize refraction for revision notes" for item in notes)

        detail_resp = client.get(f"/notes/{note_id}", headers=_auth(token))
        assert detail_resp.status_code == 200, detail_resp.text
        assert detail_resp.json()["note"]["selected_content"] == "upload:42"

        update_resp = client.put(
            f"/notes/{note_id}",
            headers=_auth(token),
            json={
                "title": "Refraction Quick Notes",
                "content": "Updated summary content.",
                "is_pinned": True,
            },
        )
        assert update_resp.status_code == 200, update_resp.text
        updated = update_resp.json()["note"]
        assert updated["title"] == "Refraction Quick Notes"
        assert updated["is_pinned"] is True

        delete_resp = client.delete(f"/notes/{note_id}", headers=_auth(token))
        assert delete_resp.status_code == 200, delete_resp.text

        list_after_delete = client.get("/notes", headers=_auth(token))
        assert list_after_delete.status_code == 200
        assert all(item["id"] != note_id for item in list_after_delete.json()["notes"])
