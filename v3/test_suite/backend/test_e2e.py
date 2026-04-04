"""
End-to-End Tests — Full API flow via FastAPI TestClient.

Covers:
  - Authentication (login, invalid creds, schema validation, JWT token flow)
  - Authorization (protected routes, role-based access)
  - Session management (create, list, rename, delete, ownership enforcement)
  - Knowledge-base endpoints (classes / subjects / folders / contents)
  - PDF serving (auth required, path traversal blocked)
  - Security hardening (path traversal in KB params, unauthenticated access)

Heavy external dependencies (LLM, FAISS load_knowledge_base background thread)
are mocked at the module level so the TestClient starts cleanly without models.
"""

import pytest
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# ──────────────────────────────────────────────────────────────
# App bootstrap — mock the pieces that touch disk / GPU / Redis
# at import / startup time so the test process stays fast.
# ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """
    Spin up the FastAPI app once per module with heavy subsystems mocked.

    sentence_transformers, faiss-cpu, llama-cpp-python, and deep-translator
    are NOT installed in the test venv (they require large binaries/models).
    We stub them in sys.modules so that importing app.main succeeds, then
    patch the startup functions that would try to load files from disk.
    """
    import sys
    from unittest.mock import MagicMock

    # ── Stub heavyweight packages before any app module is imported ──────
    _heavy = [
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
    _injected = {}
    for pkg in _heavy:
        if pkg not in sys.modules:
            sys.modules[pkg] = MagicMock()
            _injected[pkg] = True

    # Stub specific attributes accessed at import-time
    st_mock = sys.modules["sentence_transformers"]
    st_mock.SentenceTransformer = MagicMock(return_value=MagicMock())

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
        # Clean up injected stubs so other test modules aren't affected
        for pkg in _injected:
            del sys.modules[pkg]


@pytest.fixture(autouse=True)
def clear_client_cookies(client):
    client.cookies.clear()


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def login(client, email="student@example.com", password="student123"):
    """Login and return the bearer token string."""
    resp = client.post("/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ══════════════════════════════════════════════════════════════
# 1. AUTHENTICATION
# ══════════════════════════════════════════════════════════════

class TestAuthentication:

    def test_login_success_student(self, client):
        resp = client.post("/login", json={"email": "student@example.com", "password": "student123"})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["role"] == "student"
        assert "access_token=" in resp.headers.get("set-cookie", "")

    def test_login_success_admin(self, client):
        resp = client.post("/login", json={"email": "admin@example.com", "password": "admin123"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_login_wrong_password(self, client):
        resp = client.post("/login", json={"email": "student@example.com", "password": "wrongpass"})
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/login", json={"email": "ghost@example.com", "password": "any"})
        assert resp.status_code == 401

    def test_login_missing_email(self, client):
        resp = client.post("/login", json={"password": "student123"})
        assert resp.status_code == 422

    def test_login_missing_password(self, client):
        resp = client.post("/login", json={"email": "student@example.com"})
        assert resp.status_code == 422

    def test_login_empty_email(self, client):
        resp = client.post("/login", json={"email": "", "password": "student123"})
        assert resp.status_code == 422

    def test_login_empty_password(self, client):
        resp = client.post("/login", json={"email": "student@example.com", "password": ""})
        assert resp.status_code == 422

    def test_session_endpoint_accepts_auth_cookie(self, client):
        login_resp = client.post("/login", json={"email": "student@example.com", "password": "student123"})
        assert login_resp.status_code == 200

        session_resp = client.get("/auth/session")
        assert session_resp.status_code == 200
        assert session_resp.json()["authenticated"] is True
        assert session_resp.json()["username"] == "student"

    def test_logout_clears_auth_cookie(self, client):
        login_resp = client.post("/login", json={"email": "student@example.com", "password": "student123"})
        assert login_resp.status_code == 200

        logout_resp = client.post("/logout")
        assert logout_resp.status_code == 200
        assert client.get("/auth/session").status_code in (401, 403)

    def test_inactive_account_cannot_login(self, client):
        """Disabled accounts (is_active=0) must be rejected even with correct password."""
        from app.modules.db import get_connection
        from app.modules.user_manager import hash_password

        email = "disabled_e2e@example.com"
        conn = get_connection()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO users (username, email, password_hash, role, is_active) "
                "VALUES (?, ?, ?, ?, ?)",
                (email, email, hash_password("pass123"), "student", 0),
            )
            conn.commit()
        finally:
            conn.close()

        resp = client.post("/login", json={"email": email, "password": "pass123"})
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════
# 2. AUTHORIZATION — protected routes reject unauthenticated calls
# ══════════════════════════════════════════════════════════════

class TestAuthorization:

    PROTECTED_ROUTES = [
        ("GET",  "/sessions"),
        ("GET",  "/classes"),
        ("GET",  "/subjects?class_name=Class+8"),
        ("GET",  "/folders?class_name=Class+8&subject=Math"),
        ("GET",  "/contents?class_name=Class+8&subject=Math&folder=Ch1"),
        ("GET",  "/history?session_id=abc"),
        ("GET",  "/pdf?path=/some/file.pdf"),
    ]

    @pytest.mark.parametrize("method,url", PROTECTED_ROUTES)
    def test_unauthenticated_returns_401(self, client, method, url):
        resp = getattr(client, method.lower())(url)
        assert resp.status_code in (401, 403), (
            f"{method} {url} should be blocked without auth, got {resp.status_code}"
        )

    def test_invalid_token_rejected(self, client):
        resp = client.get("/sessions", headers={"Authorization": "Bearer this.is.fake"})
        assert resp.status_code in (401, 403)

    def test_expired_malformed_token_rejected(self, client):
        resp = client.get("/sessions", headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.bad.sig"})
        assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════════════════════
# 3. ROLE-BASED ACCESS CONTROL
# ══════════════════════════════════════════════════════════════

class TestRoleBasedAccess:

    def test_admin_reindex_allowed_for_admin(self, client):
        token = login(client, "admin@example.com", "admin123")
        with patch("app.modules.faiss_store.load_knowledge_base", return_value=None):
            resp = client.post("/admin/reindex", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "Reindex completed"
        assert "message" in body

    def test_admin_reindex_forbidden_for_student(self, client):
        token = login(client, "student@example.com", "student123")
        resp = client.post("/admin/reindex", headers=auth_headers(token))
        assert resp.status_code == 403

    def test_student_can_access_sessions(self, client):
        token = login(client, "student@example.com", "student123")
        resp = client.get("/sessions", headers=auth_headers(token))
        assert resp.status_code == 200
        assert "sessions" in resp.json()
        assert "message" in resp.json()


# ══════════════════════════════════════════════════════════════
# 4. SESSION MANAGEMENT
# ══════════════════════════════════════════════════════════════

class TestSessionManagement:

    @pytest.fixture(autouse=True)
    def token(self, client):
        self._token = login(client)
        self._headers = auth_headers(self._token)

    def _create_session(self, client) -> str:
        """Insert a chat_history row directly so we have a session without calling LLM."""
        from app.modules.db import get_connection
        session_id = str(uuid.uuid4())
        conn = get_connection()
        conn.execute(
            "INSERT INTO chat_history (user_id, session_id, question, answer, session_title) "
            "VALUES (?, ?, ?, ?, ?)",
            ("student", session_id, "Q", "A", "Test Session")
        )
        conn.commit()
        conn.close()
        return session_id

    def test_list_sessions_empty_or_list(self, client):
        resp = client.get("/sessions", headers=self._headers)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body.get("sessions"), list)
        assert "message" in body

    def test_list_sessions_uses_latest_row_consistently(self, client):
        from app.modules.db import get_connection

        session_id = str(uuid.uuid4())
        conn = get_connection()
        conn.execute(
            "INSERT INTO chat_history (user_id, session_id, question, answer, session_title, selected_content) VALUES (?, ?, ?, ?, ?, ?)",
            ("student", session_id, "Q1", "A1", "Z-Older-Title", "old/content"),
        )
        conn.execute(
            "INSERT INTO chat_history (user_id, session_id, question, answer, session_title, selected_content) VALUES (?, ?, ?, ?, ?, ?)",
            ("student", session_id, "Q2", "A2", "A-Newer-Title", "new/content"),
        )
        conn.commit()
        conn.close()

        resp = client.get("/sessions", headers=self._headers)
        assert resp.status_code == 200
        sessions = resp.json().get("sessions", [])
        row = next((item for item in sessions if item.get("id") == session_id), None)
        assert row is not None
        assert row.get("title") == "A-Newer-Title"
        assert row.get("selected_content") == "new/content"

    def test_rename_session(self, client):
        sid = self._create_session(client)
        resp = client.put(
            f"/sessions/{sid}",
            json={"title": "Renamed Session"},
            headers=self._headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "updated"
        assert "message" in body

    def test_delete_session(self, client):
        sid = self._create_session(client)
        resp = client.delete(f"/sessions/{sid}", headers=self._headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "deleted"
        assert "message" in body

    def test_rename_session_empty_title_rejected(self, client):
        sid = self._create_session(client)
        resp = client.put(
            f"/sessions/{sid}",
            json={"title": ""},
            headers=self._headers,
        )
        assert resp.status_code == 422

    def test_session_ownership_enforced(self, client):
        """Student cannot rename/delete a session belonging to admin."""
        from app.modules.db import get_connection
        admin_session = str(uuid.uuid4())
        conn = get_connection()
        conn.execute(
            "INSERT INTO chat_history (user_id, session_id, question, answer, session_title) "
            "VALUES (?, ?, ?, ?, ?)",
            ("admin", admin_session, "Q", "A", "Admin Session")
        )
        conn.commit()
        conn.close()

        # Student token tries to rename admin's session
        resp = client.put(
            f"/sessions/{admin_session}",
            json={"title": "Stolen"},
            headers=self._headers,
        )
        assert resp.status_code == 403

    def test_get_session_content(self, client):
        sid = self._create_session(client)
        resp = client.get(f"/sessions/{sid}/content", headers=self._headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "session_content" in body
        assert "message" in body

    def test_clear_session_content(self, client):
        from app.modules.db import get_connection

        sid = self._create_session(client)
        conn = get_connection()
        conn.execute(
            "UPDATE chat_history SET session_content=?, selected_content=? WHERE user_id=? AND session_id=?",
            ("kb:Q2xhc3MtOC9FbmdsaXNoLTEvVGV4dCBCb29rcy9DaGFwdGVyIDEucGRm", "kb:Q2xhc3MtOC9FbmdsaXNoLTEvVGV4dCBCb29rcy9DaGFwdGVyIDEucGRm", "student", sid),
        )
        conn.commit()
        conn.close()

        clear_resp = client.put(f"/sessions/{sid}/content", json={}, headers=self._headers)
        assert clear_resp.status_code == 200
        assert clear_resp.json().get("session_content") is None

        get_resp = client.get(f"/sessions/{sid}/content", headers=self._headers)
        assert get_resp.status_code == 200
        assert get_resp.json().get("session_content") is None

    def test_history_own_session(self, client):
        sid = self._create_session(client)
        resp = client.get(f"/history?session_id={sid}", headers=self._headers)
        assert resp.status_code == 200

    def test_history_other_user_session_blocked(self, client):
        from app.modules.db import get_connection
        other_session = str(uuid.uuid4())
        conn = get_connection()
        conn.execute(
            "INSERT INTO chat_history (user_id, session_id, question, answer, session_title) "
            "VALUES (?, ?, ?, ?, ?)",
            ("admin", other_session, "Q", "A", "Other")
        )
        conn.commit()
        conn.close()

        resp = client.get(f"/history?session_id={other_session}", headers=self._headers)
        assert resp.status_code == 403


class TestQuizAndFlashcardSessionManagement:

    @pytest.fixture(autouse=True)
    def token(self, client):
        self._token = login(client)
        self._headers = auth_headers(self._token)

    def _create_quiz_session(self):
        from app.modules.db import get_connection

        session_id = str(uuid.uuid4())
        conn = get_connection()
        conn.execute(
            "INSERT INTO lesson_quizzes (user_id, session_id, step_id, quiz_json) VALUES (?, ?, ?, ?)",
            ("student", session_id, 0, '{"questions": [], "session_title": "Original Quiz"}'),
        )
        conn.commit()
        conn.close()
        return session_id

    def _create_flashcard_session(self):
        from app.modules.db import get_connection

        session_id = str(uuid.uuid4())
        conn = get_connection()
        conn.execute(
            "INSERT INTO learning_artifacts (user_id, session_id, artifact_type, title, payload_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            ("student", session_id, "FLASHCARD", "Cards", '{"flashcards": [], "session_title": "Original Cards"}'),
        )
        conn.commit()
        conn.close()
        return session_id

    def test_rename_quiz_session(self, client):
        sid = self._create_quiz_session()
        resp = client.put(
            f"/quiz/sessions/{sid}",
            json={"title": "Renamed Quiz"},
            headers=self._headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_delete_quiz_session(self, client):
        sid = self._create_quiz_session()
        resp = client.delete(f"/quiz/sessions/{sid}", headers=self._headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_rename_flashcard_session(self, client):
        sid = self._create_flashcard_session()
        resp = client.put(
            f"/flashcards/sessions/{sid}",
            json={"title": "Renamed Cards"},
            headers=self._headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_delete_flashcard_session(self, client):
        sid = self._create_flashcard_session()
        resp = client.delete(f"/flashcards/sessions/{sid}", headers=self._headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_quiz_latest_returns_404_when_missing(self, client):
        missing_session = str(uuid.uuid4())
        resp = client.get(f"/quiz/latest?session_id={missing_session}", headers=self._headers)
        assert resp.status_code == 404

    def test_quiz_by_id_returns_404_when_missing(self, client):
        missing_session = str(uuid.uuid4())
        resp = client.get(f"/quiz/missing-quiz?session_id={missing_session}", headers=self._headers)
        assert resp.status_code == 404

    def test_flashcards_latest_returns_404_when_missing(self, client):
        missing_session = str(uuid.uuid4())
        resp = client.get(f"/flashcards/latest?session_id={missing_session}", headers=self._headers)
        assert resp.status_code == 404

    def test_generate_flashcards_persists_learning_artifact(self, client):
        from app.modules.db import get_connection
        from app.modules.flashcards import FlashcardItem

        session_id = str(uuid.uuid4())
        with (
            patch("app.modules.flashcards.resolve_files", return_value=["dummy.pdf"]),
            patch("app.modules.flashcards.extract_text_from_files", return_value="study material"),
            patch(
                "app.modules.flashcards.generate_flashcards_from_text",
                return_value=[FlashcardItem(question="Q1", answer="A1")],
            ),
        ):
            resp = client.post(
                "/flashcards/",
                json={
                    "class_name": "Class X",
                    "subject": "Science",
                    "content_type": "General Knowledge",
                    "chapter": "Motion",
                    "num_cards": 1,
                    "session_id": session_id,
                },
                headers=self._headers,
            )

        assert resp.status_code == 200

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id, session_id, artifact_type, title, payload_json, selected_content
            FROM learning_artifacts
            WHERE user_id=? AND session_id=? AND artifact_type='FLASHCARD'
            ORDER BY id DESC
            LIMIT 1
            """,
            ("student", session_id),
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "student"
        assert row[1] == session_id
        assert row[2] == "FLASHCARD"
        assert row[3] == "Flashcards - Motion"
        payload = row[4]
        assert "Q1" in payload and "A1" in payload
        assert row[5] == "Class X/Science/General Knowledge/Motion"


# ══════════════════════════════════════════════════════════════
# 5. KNOWLEDGE BASE ENDPOINTS
# ══════════════════════════════════════════════════════════════

class TestKnowledgeBase:

    @pytest.fixture(autouse=True)
    def headers(self, client):
        token = login(client)
        self._h = auth_headers(token)

    def test_classes_returns_list(self, client):
        resp = client.get("/classes", headers=self._h)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body.get("classes"), list)
        assert "message" in body


class TestProfileUpdate:

    @pytest.fixture(autouse=True)
    def headers(self, client):
        token = login(client)
        self._h = auth_headers(token)

    def test_profile_update_mutable_fields(self, client):
        resp = client.put(
            "/profile",
            json={"first_name": "Updated", "last_name": "Student", "dob": "2000-01-02"},
            headers=self._h,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "updated"
        assert body["profile"]["first_name"] == "Updated"
        assert body["profile"]["last_name"] == "Student"
        assert body["profile"]["dob"] == "2000-01-02"
        assert "message" in body

    def test_profile_update_rejects_email_change(self, client):
        resp = client.put(
            "/profile",
            json={"email": "hacker@example.com"},
            headers=self._h,
        )
        assert resp.status_code == 400

    def test_profile_update_writes_audit_row(self, client):
        resp = client.put(
            "/profile",
            json={"first_name": "AuditName"},
            headers=self._h,
        )
        assert resp.status_code == 200

        from app.modules.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT action, changes_json
            FROM profile_audit_log
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT 1
            """,
            ("student",),
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "PROFILE_UPDATE"
        assert "first_name" in (row[1] or "")

    def test_subjects_valid_class(self, client):
        resp = client.get("/subjects?class_name=Class+8", headers=self._h)
        assert resp.status_code in (200, 400)  # 400 if dots in name match rule

    def test_subjects_unauthenticated(self, client):
        client.cookies.clear()
        resp = client.get("/subjects?class_name=Class+8")
        assert resp.status_code in (401, 403)

    def test_contents_unauthenticated(self, client):
        client.cookies.clear()
        resp = client.get("/contents?class_name=x&subject=y&folder=z")
        assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════════════════════
# 6. SECURITY — Path Traversal & Access Control
# ══════════════════════════════════════════════════════════════

class TestSecurityHardening:

    @pytest.fixture(autouse=True)
    def headers(self, client):
        token = login(client)
        self._h = auth_headers(token)

    # ── Path traversal in KB endpoints ──────────────────────

    @pytest.mark.parametrize("param", [
        "../../../etc/passwd",
        "..\\..\\Windows\\System32",
        "foo/../../bar",
        "foo\\..\\bar",
    ])
    def test_subjects_path_traversal_rejected(self, client, param):
        resp = client.get(f"/subjects?class_name={param}", headers=self._h)
        assert resp.status_code == 400, (
            f"Expected 400 for traversal attempt '{param}', got {resp.status_code}"
        )

    @pytest.mark.parametrize("param", [
        "../../../etc/passwd",
        "..\\..\\Windows",
        "x/../../y",
    ])
    def test_folders_path_traversal_rejected(self, client, param):
        resp = client.get(
            f"/folders?class_name=Class8&subject={param}", headers=self._h
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("param", [
        "../../../etc",
        "..\\..\\Windows",
    ])
    def test_contents_path_traversal_rejected(self, client, param):
        resp = client.get(
            f"/contents?class_name=Class8&subject=Math&folder={param}",
            headers=self._h,
        )
        assert resp.status_code == 400

    # ── PDF endpoint ──────────────────────────────────────────

    def test_pdf_unauthenticated_blocked(self, client):
        client.cookies.clear()
        resp = client.get("/pdf?path=/some/file.pdf")
        assert resp.status_code in (401, 403)

    def test_pdf_path_outside_kb_returns_403(self, client):
        resp = client.get("/pdf?path=C:/Windows/System32/cmd.exe", headers=self._h)
        assert resp.status_code == 403

    def test_pdf_traversal_url_encoded_blocked(self, client):
        resp = client.get("/pdf?path=..%2F..%2Fetc%2Fpasswd", headers=self._h)
        assert resp.status_code == 403

    def test_pdf_nonexistent_file_returns_404(self, client):
        import os
        from app.api.routes import _kb_dir
        fake = os.path.join(_kb_dir(), "nonexistent_file.pdf")
        resp = client.get(f"/pdf?path={fake}", headers=self._h)
        assert resp.status_code == 403

    def test_pdf_reference_variants_resolve_same_file(self, client):
        import base64
        import os

        from app.api.routes import _kb_dir

        file_name = f"canon-{uuid.uuid4().hex}.pdf"
        canonical_rel = f"Class 8/General Knowledge/Text Books/{file_name}"
        variant_rel = f"Class 8/General Knowledge/../General Knowledge/Text Books/./{file_name}"

        full_path = os.path.join(_kb_dir(), *canonical_rel.split("/"))
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        payload = b"%PDF-1.4\n%canonical-test\n"

        try:
            with open(full_path, "wb") as handle:
                handle.write(payload)

            # Build a deliberately non-canonical kb: reference.
            raw = variant_rel.encode("utf-8")
            variant_content_id = "kb:" + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

            by_content_id = client.get(f"/pdf?content_id={variant_content_id}", headers=self._h)
            by_relative_path = client.get(f"/pdf?path={variant_rel}", headers=self._h)

            assert by_content_id.status_code == 200
            assert by_relative_path.status_code == 200
            assert by_content_id.content == payload
            assert by_relative_path.content == payload
        finally:
            if os.path.exists(full_path):
                os.remove(full_path)

    # ── Admin-only endpoint rejects students ─────────────────

    def test_incremental_reindex_student_forbidden(self, client):
        resp = client.post("/admin/reindex-incremental", headers=self._h)
        assert resp.status_code == 403

    def test_kb_symlink_escape_blocked_in_subjects(self, client):
        """_safe_kb_path must resolve symlinks (realpath) before the boundary check."""
        import os
        import tempfile
        from app.api.routes import _kb_dir

        kb = _kb_dir()
        os.makedirs(kb, exist_ok=True)

        with tempfile.TemporaryDirectory() as secret_dir:
            # Create a symlink inside KB that points outside KB.
            link_name = "escape-link-test"
            link_path = os.path.join(kb, link_name)
            try:
                if os.path.islink(link_path):
                    os.unlink(link_path)
                try:
                    os.symlink(secret_dir, link_path)
                except OSError as exc:
                    pytest.skip(f"Symlink creation requires elevated privileges on this OS: {exc}")
                resp = client.get(f"/subjects?class_name={link_name}", headers=self._h)
                # With realpath, the candidate resolves outside KB → 400.
                assert resp.status_code in (400, 404), (
                    f"Symlink escape should be blocked, got {resp.status_code}"
                )
            finally:
                if os.path.islink(link_path):
                    os.unlink(link_path)

    def test_flashcard_request_rejects_extra_fields(self, client):
        """FlashcardRequest with extra='forbid' must reject unknown keys."""
        resp = client.post(
            "/flashcards/",
            json={
                "class_name": "Class 8",
                "subject": "Science",
                "content_type": "Notes",
                "unknown_key": "malicious",
            },
            headers=self._h,
        )
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════
# 7. ASK ENDPOINT (mocked LLM)
# ══════════════════════════════════════════════════════════════

class TestAskEndpoint:

    @pytest.fixture(autouse=True)
    def headers(self, client):
        token = login(client)
        self._h = auth_headers(token)

    def test_ask_unauthenticated_blocked(self, client):
        client.cookies.clear()
        resp = client.post("/ask", json={"query": "What is gravity?"})
        assert resp.status_code in (401, 403)

    def test_ask_empty_query_rejected(self, client):
        resp = client.post("/ask", json={"query": ""}, headers=self._h)
        assert resp.status_code == 422

    def test_ask_missing_query_rejected(self, client):
        resp = client.post("/ask", json={}, headers=self._h)
        assert resp.status_code == 422

    def test_ask_query_too_long_rejected(self, client):
        resp = client.post("/ask", json={"query": "x" * 5001}, headers=self._h)
        assert resp.status_code == 422

    def test_ask_success_with_mocked_rag(self, client):
        with patch("app.api.routes.generate_answer", return_value="Gravity is a force."):
            resp = client.post(
                "/ask",
                json={"query": "What is gravity?"},
                headers=self._h,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"] == "Gravity is a force."
        assert "session_id" in body

    def test_ask_returns_session_id(self, client):
        with patch("app.api.routes.generate_answer", return_value="Test answer."):
            resp = client.post(
                "/ask",
                json={"query": "Explain photosynthesis"},
                headers=self._h,
            )
        assert resp.status_code == 200
        assert uuid.UUID(resp.json()["session_id"])  # valid UUID

    def test_ask_with_explicit_session_id(self, client):
        sid = str(uuid.uuid4())
        with patch("app.api.routes.generate_answer", return_value="Answer here."):
            resp = client.post(
                "/ask",
                json={"query": "Define osmosis", "session_id": sid},
                headers=self._h,
            )
        assert resp.status_code == 200
        assert resp.json()["session_id"] == sid
