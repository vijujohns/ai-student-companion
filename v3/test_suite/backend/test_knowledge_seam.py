"""
Knowledge + Ingestion extraction seam tests — Phase 2.

Verifies that:
  - KB browsing routes (/classes, /subjects, /folders, /contents) delegate
    to services.knowledge rather than inlining filesystem logic.
  - File management routes (/files/tree, /files/index-status, /files/reindex)
    delegate to services.knowledge.
  - DefaultKnowledgeService path-traversal guard raises ValueError.
  - DefaultKnowledgeService list_* methods return expected shapes.
"""

import sys
import os
import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

# ─── path bootstrap ───────────────────────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))


def _setup_db():
    from app.modules.db import init_db
    init_db()


# =============================================================================
# Unit tests — DefaultKnowledgeService
# =============================================================================

class TestDefaultKnowledgeServiceUnit:
    """Tests for the in-process knowledge adapter (no HTTP)."""

    @classmethod
    def setup_class(cls):
        _setup_db()

    def _make_service(self, tmp_path: str):
        from app.modules.adapters.default_services import DefaultKnowledgeService
        return DefaultKnowledgeService(kb_dir=tmp_path)

    def test_list_classes_empty_when_kb_missing(self, tmp_path):
        svc = self._make_service(str(tmp_path / "no_such_kb"))
        assert svc.list_classes() == []

    def test_list_classes_returns_directories(self, tmp_path):
        (tmp_path / "Class X").mkdir()
        (tmp_path / "Class Y").mkdir()
        (tmp_path / "not_a_dir.txt").write_text("x")
        svc = self._make_service(str(tmp_path))
        result = svc.list_classes()
        assert result == ["Class X", "Class Y"]

    def test_list_subjects_returns_empty_for_missing_class(self, tmp_path):
        svc = self._make_service(str(tmp_path))
        assert svc.list_subjects("Nonexistent") == []

    def test_list_subjects_lists_sub_dirs(self, tmp_path):
        class_dir = tmp_path / "Class X"
        (class_dir / "Math").mkdir(parents=True)
        (class_dir / "Science").mkdir()
        svc = self._make_service(str(tmp_path))
        assert svc.list_subjects("Class X") == ["Math", "Science"]

    def test_list_folders_returns_empty_for_missing_subject(self, tmp_path):
        (tmp_path / "Class X").mkdir()
        svc = self._make_service(str(tmp_path))
        assert svc.list_folders("Class X", "NoSubject") == []

    def test_list_folders_lists_sub_dirs(self, tmp_path):
        base = tmp_path / "Class X" / "Math"
        (base / "Chapter1").mkdir(parents=True)
        (base / "Chapter2").mkdir()
        svc = self._make_service(str(tmp_path))
        assert svc.list_folders("Class X", "Math") == ["Chapter1", "Chapter2"]

    def test_path_traversal_raises_value_error(self, tmp_path):
        svc = self._make_service(str(tmp_path))
        with pytest.raises(ValueError):
            svc.list_subjects("../outside")

    def test_path_traversal_with_backslash_raises_value_error(self, tmp_path):
        svc = self._make_service(str(tmp_path))
        with pytest.raises(ValueError):
            svc.list_subjects("foo\\..\\bar")

    def test_list_contents_returns_empty_for_missing_folder(self, tmp_path):
        svc = self._make_service(str(tmp_path))
        assert svc.list_contents("Class X", "Math", "Ch1") == []

    def test_list_contents_only_returns_pdfs(self, tmp_path):
        folder = tmp_path / "Class X" / "Math" / "Ch1"
        folder.mkdir(parents=True)
        (folder / "textbook.pdf").write_bytes(b"%PDF")
        (folder / "notes.txt").write_text("notes")
        svc = self._make_service(str(tmp_path))
        result = svc.list_contents("Class X", "Math", "Ch1")
        assert len(result) == 1
        assert result[0]["title"] == "textbook"
        assert "content_id" in result[0]


# =============================================================================
# Route seam tests — KB browsing routes use services.knowledge
# =============================================================================

@pytest.fixture(scope="module")
def client():
    """Lightweight test client with heavy deps mocked."""
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
def clear_cookies(client):
    client.cookies.clear()


def _login(client):
    resp = client.post("/login", json={"email": "student@example.com", "password": "student123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestKnowledgeRouteSeam:
    """Verify routes delegate to services.knowledge and not inline logic."""

    def test_classes_route_uses_knowledge_service(self, client):
        token = _login(client)
        stub = ["Class A", "Class B"]
        with patch("app.api.routes.services") as mock_svc:
            mock_svc.knowledge.list_classes.return_value = stub
            resp = client.get("/classes", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["classes"] == stub
        mock_svc.knowledge.list_classes.assert_called_once()

    def test_subjects_route_uses_knowledge_service(self, client):
        token = _login(client)
        stub = ["Math", "Science"]
        with patch("app.api.routes.services") as mock_svc:
            mock_svc.knowledge.list_subjects.return_value = stub
            resp = client.get("/subjects", params={"class_name": "Class X"}, headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["subjects"] == stub
        mock_svc.knowledge.list_subjects.assert_called_once_with("Class X")

    def test_folders_route_uses_knowledge_service(self, client):
        token = _login(client)
        stub = ["Chapter1", "Chapter2"]
        with patch("app.api.routes.services") as mock_svc:
            mock_svc.knowledge.list_folders.return_value = stub
            resp = client.get(
                "/folders",
                params={"class_name": "Class X", "subject": "Math"},
                headers=_auth(token),
            )
        assert resp.status_code == 200
        assert resp.json()["folders"] == stub
        mock_svc.knowledge.list_folders.assert_called_once_with("Class X", "Math")

    def test_contents_route_uses_knowledge_service(self, client):
        token = _login(client)
        stub = [{"title": "Textbook", "content_id": "kb:abc123"}]
        with patch("app.api.routes.services") as mock_svc:
            mock_svc.knowledge.list_contents.return_value = stub
            resp = client.get(
                "/contents",
                params={"class_name": "Class X", "subject": "Math", "folder": "Chapter1"},
                headers=_auth(token),
            )
        assert resp.status_code == 200
        assert resp.json()["contents"] == stub
        mock_svc.knowledge.list_contents.assert_called_once_with("Class X", "Math", "Chapter1")

    def test_file_tree_route_uses_knowledge_service(self, client):
        token = _login(client)
        stub = [{"file_id": 1, "display_name": "doc.pdf"}]
        with patch("app.api.routes.services") as mock_svc:
            mock_svc.knowledge.file_tree.return_value = stub
            resp = client.get("/files/tree", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["items"] == stub
        mock_svc.knowledge.file_tree.assert_called_once()

    def test_index_status_route_uses_knowledge_service(self, client):
        token = _login(client)
        stub = [{"file_id": 1, "status": "indexed"}]
        with patch("app.api.routes.services") as mock_svc:
            mock_svc.knowledge.index_status.return_value = stub
            resp = client.get("/files/index-status", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["items"] == stub
        mock_svc.knowledge.index_status.assert_called_once()

    def test_path_traversal_returns_400(self, client):
        token = _login(client)
        with patch("app.api.routes.services") as mock_svc:
            mock_svc.knowledge.list_subjects.side_effect = ValueError("Invalid path")
            resp = client.get("/subjects", params={"class_name": "../evil"}, headers=_auth(token))
        assert resp.status_code == 400
