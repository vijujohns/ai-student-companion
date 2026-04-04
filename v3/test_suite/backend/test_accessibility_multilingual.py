"""
Tests — Accessibility, Multilingual (translation), OCR, and User Preferences.

Unit tests:
  - translation module: translate_text, list_languages, SUPPORTED_LANGUAGES
  - ocr module: get_ocr_status, extract_text_from_image edge cases, is_image_file
  - file_management: _validate_file_upload accepts images, rejects non-images
  - db schema: user_preferences table exists and upserts work

API integration tests:
  - GET  /languages        — public endpoint, returns list
  - POST /translate        — authenticated, valid target, unknown target → 422
  - GET  /preferences      — authenticated; unauthenticated → 401
  - PUT  /preferences      — valid language persists, unknown language → 422
  - GET  /ocr/status       — authenticated, returns shape
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# ─── path bootstrap ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))


# ─── DB setup helper ─────────────────────────────────────────────────────────
def _setup_db():
    from app.modules.db import init_db
    init_db()


# =============================================================================
# Unit — translation module
# =============================================================================

class TestTranslationModule:
    def test_list_languages_returns_list(self):
        from app.modules.translation import list_languages
        langs = list_languages()
        assert isinstance(langs, list)
        assert len(langs) > 0

    def test_list_languages_entry_shape(self):
        from app.modules.translation import list_languages
        first = list_languages()[0]
        assert "code" in first
        assert "name" in first
        assert isinstance(first["code"], str)
        assert isinstance(first["name"], str)

    def test_supported_languages_has_english(self):
        from app.modules.translation import SUPPORTED_LANGUAGES
        assert "en" in SUPPORTED_LANGUAGES
        assert SUPPORTED_LANGUAGES["en"] == "English"

    def test_supported_languages_has_hindi(self):
        from app.modules.translation import SUPPORTED_LANGUAGES
        assert "hi" in SUPPORTED_LANGUAGES

    def test_translate_text_same_language_returns_original(self):
        from app.modules.translation import translate_text
        # source == target → no-op
        result = translate_text("hello", target="en", source="en")
        assert result == "hello"

    def test_translate_text_empty_input_returns_empty(self):
        from app.modules.translation import translate_text
        assert translate_text("", target="en") == ""

    def test_translate_text_unknown_target_falls_back_to_en(self):
        """Unknown language codes should not raise — they fall back to 'en'."""
        from app.modules.translation import translate_text
        with patch("app.modules.translation.GoogleTranslator") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.translate.return_value = "hello"
            mock_cls.return_value = mock_instance
            result = translate_text("bonjour", target="xx_invalid_code")
        # Should not raise, result is a string
        assert isinstance(result, str)

    def test_translate_text_returns_string_on_network_error(self):
        """When GoogleTranslator raises, translate_text returns original text."""
        from app.modules.translation import translate_text
        with patch("app.modules.translation.GoogleTranslator", side_effect=Exception("network error")):
            result = translate_text("test text", target="hi")
        assert result == "test text"

    def test_translate_backward_compat_alias(self):
        """Old translate() alias should still work."""
        from app.modules.translation import translate
        with patch("app.modules.translation.GoogleTranslator") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.translate.return_value = "नमस्ते"
            mock_cls.return_value = mock_instance
            result = translate("hello", target="hi")
        assert isinstance(result, str)

    def test_translate_fallback_phrase(self):
        """Fallback dict phrase is returned when translator raises."""
        from app.modules.translation import translate_text
        with patch("app.modules.translation.GoogleTranslator", side_effect=Exception("offline")):
            result = translate_text("namaste", target="en")
        assert result == "hello"


# =============================================================================
# Unit — OCR module
# =============================================================================

class TestOcrModule:
    def test_get_ocr_status_returns_dict(self):
        from app.modules.ocr import get_ocr_status
        status = get_ocr_status()
        assert "available" in status
        assert "engine" in status
        assert "message" in status
        assert isinstance(status["available"], bool)

    def test_get_ocr_status_engine_field(self):
        from app.modules.ocr import get_ocr_status
        status = get_ocr_status()
        assert status["engine"] in ("tesseract", "none")

    def test_is_image_file_accepts_jpeg(self):
        from app.modules.ocr import is_image_file
        assert is_image_file("/path/to/photo.jpg") is True
        assert is_image_file("/path/to/photo.jpeg") is True

    def test_is_image_file_accepts_png(self):
        from app.modules.ocr import is_image_file
        assert is_image_file("/path/to/image.png") is True

    def test_is_image_file_accepts_gif_webp(self):
        from app.modules.ocr import is_image_file
        assert is_image_file("/path/to/anim.gif") is True
        assert is_image_file("/path/to/image.webp") is True

    def test_is_image_file_rejects_pdf(self):
        from app.modules.ocr import is_image_file
        assert is_image_file("/path/to/doc.pdf") is False

    def test_is_image_file_rejects_txt(self):
        from app.modules.ocr import is_image_file
        assert is_image_file("/path/to/notes.txt") is False

    def test_extract_text_returns_empty_for_missing_file(self):
        from app.modules.ocr import extract_text_from_image
        result = extract_text_from_image("/nonexistent/path/image.png")
        assert result == ""

    def test_extract_text_returns_empty_for_non_image_extension(self):
        from app.modules.ocr import extract_text_from_image
        result = extract_text_from_image("/some/file.pdf")
        assert result == ""

    def test_extract_text_returns_empty_when_ocr_unavailable(self):
        """When OCR is unavailable, returns empty string without raising."""
        from app.modules.ocr import extract_text_from_image
        import tempfile, os
        # Create a temporary valid-name image file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n")  # minimal PNG header bytes
            tmp = f.name
        try:
            with patch("app.modules.ocr._check_ocr_available", return_value=False):
                # reset the cached value so the patch takes effect
                import app.modules.ocr as ocr_mod
                ocr_mod._OCR_AVAILABLE = None
                result = extract_text_from_image(tmp)
            assert result == ""
        finally:
            os.unlink(tmp)
            import app.modules.ocr as ocr_mod
            ocr_mod._OCR_AVAILABLE = None   # reset for other tests

    def test_allowed_image_mime_types_has_jpeg_png(self):
        from app.modules.ocr import ALLOWED_IMAGE_MIME_TYPES
        assert "image/jpeg" in ALLOWED_IMAGE_MIME_TYPES
        assert "image/png" in ALLOWED_IMAGE_MIME_TYPES


# =============================================================================
# Unit — file_management validation
# =============================================================================

class TestFileManagementImageValidation:
    def _make_upload(self, filename, content_type):
        from fastapi import UploadFile
        import io
        mock = MagicMock(spec=UploadFile)
        mock.filename = filename
        mock.content_type = content_type
        mock.file = io.BytesIO(b"fake")
        return mock

    def test_validate_file_upload_accepts_pdf(self):
        from app.modules.file_management import _validate_file_upload
        upload = self._make_upload("doc.pdf", "application/pdf")
        ext = _validate_file_upload(upload)
        assert ext == ".pdf"

    def test_validate_file_upload_accepts_jpeg(self):
        from app.modules.file_management import _validate_file_upload
        upload = self._make_upload("photo.jpg", "image/jpeg")
        ext = _validate_file_upload(upload)
        assert ext == ".jpg"

    def test_validate_file_upload_accepts_png(self):
        from app.modules.file_management import _validate_file_upload
        upload = self._make_upload("diagram.png", "image/png")
        ext = _validate_file_upload(upload)
        assert ext == ".png"

    def test_validate_file_upload_accepts_webp(self):
        from app.modules.file_management import _validate_file_upload
        upload = self._make_upload("image.webp", "image/webp")
        ext = _validate_file_upload(upload)
        assert ext == ".webp"

    def test_validate_file_upload_rejects_txt(self):
        from app.modules.file_management import _validate_file_upload
        from fastapi import HTTPException
        upload = self._make_upload("notes.txt", "text/plain")
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_upload(upload)
        assert exc_info.value.status_code == 400

    def test_validate_file_upload_rejects_docx(self):
        from app.modules.file_management import _validate_file_upload
        from fastapi import HTTPException
        upload = self._make_upload("report.docx", "application/vnd.openxmlformats")
        with pytest.raises(HTTPException):
            _validate_file_upload(upload)


# =============================================================================
# Unit — DB schema for user_preferences
# =============================================================================

class TestUserPreferencesSchema:
    @classmethod
    def setup_class(cls):
        _setup_db()

    def test_user_preferences_table_exists(self):
        from app.modules.db import get_connection
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")
            row = cur.fetchone()
        finally:
            conn.close()
        assert row is not None

    def test_insert_and_retrieve_preference(self):
        from app.modules.db import get_connection
        from datetime import datetime, timezone
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO user_preferences (user_id, preferred_language, updated_at) VALUES (?,?,?)",
                ("pref_test_user", "hi", datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            cur.execute("SELECT preferred_language FROM user_preferences WHERE user_id='pref_test_user'")
            row = cur.fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == "hi"

    def test_upsert_updates_language(self):
        from app.modules.db import get_connection
        from datetime import datetime, timezone
        conn = get_connection()
        try:
            cur = conn.cursor()
            # Insert
            cur.execute(
                "INSERT OR REPLACE INTO user_preferences (user_id, preferred_language, updated_at) VALUES (?,?,?)",
                ("upsert_u", "en", datetime.now(timezone.utc).isoformat()),
            )
            # Update via REPLACE
            cur.execute(
                "INSERT OR REPLACE INTO user_preferences (user_id, preferred_language, updated_at) VALUES (?,?,?)",
                ("upsert_u", "ta", datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            cur.execute("SELECT preferred_language FROM user_preferences WHERE user_id='upsert_u'")
            row = cur.fetchone()
        finally:
            conn.close()
        assert row[0] == "ta"


# =============================================================================
# API integration tests
# =============================================================================

@pytest.fixture(scope="module")
def client():
    """TestClient with heavy deps mocked."""
    _heavy = [
        "sentence_transformers", "faiss", "numpy", "numpy.core",
        "tqdm", "tqdm.auto", "pypdf", "deep_translator",
        "llama_cpp", "openai", "docx", "python_docx",
    ]
    _injected = {}
    for pkg in _heavy:
        if pkg not in sys.modules:
            sys.modules[pkg] = MagicMock()
            _injected[pkg] = True

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
        for pkg in _injected:
            del sys.modules[pkg]


@pytest.fixture(autouse=True)
def clear_cookies(client):
    client.cookies.clear()


def _login(client, email="student@example.com", password="student123"):
    resp = client.post("/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestLanguagesRoute:
    def test_get_languages_returns_200(self, client):
        token = _login(client)
        resp = client.get("/languages", headers=_auth(token))
        assert resp.status_code == 200

    def test_get_languages_returns_list(self, client):
        token = _login(client)
        resp = client.get("/languages", headers=_auth(token))
        body = resp.json()
        assert "languages" in body
        assert isinstance(body["languages"], list)
        assert len(body["languages"]) > 0

    def test_get_languages_entry_has_code_and_name(self, client):
        token = _login(client)
        resp = client.get("/languages", headers=_auth(token))
        first = resp.json()["languages"][0]
        assert "code" in first
        assert "name" in first

    def test_get_languages_includes_english(self, client):
        token = _login(client)
        resp = client.get("/languages", headers=_auth(token))
        codes = [l["code"] for l in resp.json()["languages"]]
        assert "en" in codes


class TestTranslateRoute:
    def test_translate_unauthenticated_returns_401(self, client):
        client.cookies.clear()
        resp = client.post("/translate", json={"text": "Hello", "target_language": "hi"})
        assert resp.status_code in (401, 403)

    def test_translate_valid_returns_200(self, client):
        token = _login(client)
        with patch("app.modules.translation.GoogleTranslator") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.translate.return_value = "नमस्ते"
            mock_cls.return_value = mock_instance
            resp = client.post(
                "/translate",
                headers=_auth(token),
                json={"text": "Hello", "target_language": "hi"},
            )
        assert resp.status_code == 200

    def test_translate_response_contains_translated_text(self, client):
        token = _login(client)
        with patch("app.modules.translation.GoogleTranslator") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.translate.return_value = "नमस्ते"
            mock_cls.return_value = mock_instance
            resp = client.post(
                "/translate",
                headers=_auth(token),
                json={"text": "Hello", "target_language": "hi"},
            )
        body = resp.json()
        assert "translated_text" in body
        assert body["target_language"] == "hi"

    def test_translate_unknown_language_returns_422(self, client):
        token = _login(client)
        resp = client.post(
            "/translate",
            headers=_auth(token),
            json={"text": "Hello", "target_language": "xx_notreal"},
        )
        assert resp.status_code == 422

    def test_translate_empty_text_returns_422(self, client):
        token = _login(client)
        resp = client.post(
            "/translate",
            headers=_auth(token),
            json={"text": "", "target_language": "hi"},
        )
        assert resp.status_code == 422


class TestPreferencesRoute:
    def test_get_preferences_unauthenticated_returns_401(self, client):
        client.cookies.clear()
        resp = client.get("/preferences")
        assert resp.status_code in (401, 403)

    def test_get_preferences_authenticated_returns_200(self, client):
        token = _login(client)
        resp = client.get("/preferences", headers=_auth(token))
        assert resp.status_code == 200

    def test_get_preferences_has_preferred_language(self, client):
        token = _login(client)
        resp = client.get("/preferences", headers=_auth(token))
        body = resp.json()
        assert "preferred_language" in body
        assert isinstance(body["preferred_language"], str)

    def test_put_preferences_updates_language(self, client):
        token = _login(client)
        resp = client.put(
            "/preferences",
            headers=_auth(token),
            json={"preferred_language": "ta"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("preferred_language") == "ta"
        assert body.get("updated") is True

    def test_put_preferences_unknown_language_returns_422(self, client):
        token = _login(client)
        resp = client.put(
            "/preferences",
            headers=_auth(token),
            json={"preferred_language": "zz_invalid"},
        )
        assert resp.status_code == 422

    def test_put_then_get_preference_persists(self, client):
        token = _login(client)
        client.put(
            "/preferences",
            headers=_auth(token),
            json={"preferred_language": "ml"},
        )
        resp = client.get("/preferences", headers=_auth(token))
        assert resp.json()["preferred_language"] == "ml"

    def test_put_preferences_can_store_reminder_settings(self, client):
        token = _login(client)
        resp = client.put(
            "/preferences",
            headers=_auth(token),
            json={
                "preferred_language": "en",
                "reminder_settings": {
                    "enabled": False,
                    "frequency": "important-only",
                    "muted_ids": ["assessment-reminder"],
                },
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["reminder_settings"]["enabled"] is False
        assert body["reminder_settings"]["frequency"] == "important-only"

        stored = client.get("/preferences", headers=_auth(token))
        assert stored.status_code == 200
        assert stored.json()["reminder_settings"]["muted_ids"] == ["assessment-reminder"]


class TestOcrStatusRoute:
    def test_ocr_status_unauthenticated_returns_401(self, client):
        client.cookies.clear()
        resp = client.get("/ocr/status")
        assert resp.status_code in (401, 403)

    def test_ocr_status_authenticated_returns_200(self, client):
        token = _login(client)
        resp = client.get("/ocr/status", headers=_auth(token))
        assert resp.status_code == 200

    def test_ocr_status_response_shape(self, client):
        token = _login(client)
        resp = client.get("/ocr/status", headers=_auth(token))
        body = resp.json()
        assert "available" in body
        assert "engine" in body
        assert "message" in body

    def test_ocr_status_available_is_bool(self, client):
        token = _login(client)
        resp = client.get("/ocr/status", headers=_auth(token))
        assert isinstance(resp.json()["available"], bool)
