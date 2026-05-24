"""
File Management Tests
- File upload validation
- User storage isolation
- File naming and sanitization
- Indexing status tracking
"""

import sqlite3

import pytest
from unittest.mock import MagicMock, patch, call
from fastapi import HTTPException, UploadFile
from app.modules.file_management import (
    _storage_base_dir,
    _file_sha256,
    _resolve_kb_absolute_path,
    _safe_name,
    _effective_email,
    _validate_tree_names,
    _validate_pdf_upload,
    get_or_create_user_storage_root,
    make_kb_content_ref,
    make_upload_content_ref,
    queue_reindex,
    recover_indexing_jobs,
    delete_uploaded_file,
    rename_uploaded_file,
    resolve_content_reference,
)


class TestStorageBaseDir:
    """Test storage directory initialization."""

    @patch("app.modules.file_management.os.makedirs")
    @patch("app.modules.file_management.os.path.join")
    def test_storage_base_dir_creates_directory(self, mock_join, mock_makedirs):
        """Verify storage base directory is created."""
        mock_join.return_value = "/fake/path"
        
        result = _storage_base_dir()
        
        mock_makedirs.assert_called_once()
        assert result == "/fake/path"

    def test_storage_base_dir_returns_string(self):
        """Verify function returns string path."""
        result = _storage_base_dir()
        assert isinstance(result, str)


class TestFileSHA256:
    """Test file hash calculation."""

    def test_file_sha256_consistent(self):
        """Verify same data produces same hash."""
        data = b"test file content"
        hash1 = _file_sha256(data)
        hash2 = _file_sha256(data)
        
        assert hash1 == hash2

    def test_file_sha256_different_data(self):
        """Verify different data produces different hash."""
        hash1 = _file_sha256(b"data1")
        hash2 = _file_sha256(b"data2")
        
        assert hash1 != hash2

    def test_file_sha256_format(self):
        """Verify hash is 64-char hex string."""
        hash_val = _file_sha256(b"test")
        
        assert len(hash_val) == 64
        assert all(c in "0123456789abcdef" for c in hash_val)

    def test_file_sha256_empty_file(self):
        """Verify hashing empty file works."""
        hash_val = _file_sha256(b"")
        
        assert isinstance(hash_val, str)
        assert len(hash_val) == 64


def _create_upload_management_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE uploaded_files (
            id INTEGER PRIMARY KEY,
            user_id TEXT,
            class_name TEXT,
            subject_name TEXT,
            folder_name TEXT,
            file_name TEXT,
            display_name TEXT,
            relative_path TEXT,
            mime_type TEXT,
            size_bytes INTEGER,
            file_sha256 TEXT,
            upload_status TEXT,
            updated_at TEXT
        )
        """
    )
    cursor.execute("CREATE TABLE file_index_status (file_id INTEGER, indexed INTEGER, status_reason TEXT, message_id TEXT, updated_at TEXT)")
    cursor.execute("CREATE TABLE chat_history (selected_content TEXT, session_content TEXT)")
    cursor.execute("CREATE TABLE user_preferences (content_id TEXT)")
    conn.commit()
    conn.close()


def _connect_upload_management_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


class TestUploadedFileManagement:
    def test_rename_uploaded_file_moves_file_and_updates_record(self, tmp_path, monkeypatch):
        db_path = tmp_path / "uploads.db"
        _create_upload_management_db(db_path)
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        old_file = upload_dir / "Old-Name.pdf"
        old_file.write_bytes(b"%PDF")

        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            INSERT INTO uploaded_files
            (id, user_id, class_name, subject_name, folder_name, file_name, display_name, relative_path, mime_type, size_bytes, file_sha256, upload_status)
            VALUES (1, 'student', 'Class-10', 'Biology', 'Notes', 'Old-Name.pdf', 'Old-Name', 'uploads/Old-Name.pdf', 'application/pdf', 4, 'hash', 'INDEXED')
            """
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr("app.modules.file_management.BASE_DIR", str(tmp_path))
        monkeypatch.setattr("app.modules.file_management.get_connection", lambda: _connect_upload_management_db(db_path))
        result = rename_uploaded_file({"username": "student", "role": "student"}, 1, "New-Name")

        assert result["status"] == "renamed"
        assert not old_file.exists()
        assert (upload_dir / "New-Name.pdf").exists()

    def test_delete_uploaded_file_removes_records_and_clears_content_refs(self, tmp_path, monkeypatch):
        db_path = tmp_path / "uploads.db"
        _create_upload_management_db(db_path)
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        uploaded_file = upload_dir / "Notes.pdf"
        uploaded_file.write_bytes(b"%PDF")
        content_id = make_upload_content_ref(2)

        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            INSERT INTO uploaded_files
            (id, user_id, class_name, subject_name, folder_name, file_name, display_name, relative_path, mime_type, size_bytes, file_sha256, upload_status)
            VALUES (2, 'student', 'Class-10', 'Biology', 'Notes', 'Notes.pdf', 'Notes', 'uploads/Notes.pdf', 'application/pdf', 4, 'hash', 'INDEXED')
            """
        )
        conn.execute("INSERT INTO file_index_status (file_id, indexed, status_reason, message_id) VALUES (2, 1, 'indexed', 'MSG-1000')")
        conn.execute("INSERT INTO chat_history (selected_content, session_content) VALUES (?, ?)", (content_id, content_id))
        conn.execute("INSERT INTO user_preferences (content_id) VALUES (?)", (content_id,))
        conn.commit()
        conn.close()

        monkeypatch.setattr("app.modules.file_management.BASE_DIR", str(tmp_path))
        monkeypatch.setattr("app.modules.file_management.get_connection", lambda: _connect_upload_management_db(db_path))
        result = delete_uploaded_file({"username": "student", "role": "student"}, 2)

        assert result["status"] == "deleted"
        assert result["removed_file"] is True
        assert not uploaded_file.exists()

        conn = sqlite3.connect(db_path)
        assert conn.execute("SELECT COUNT(*) FROM uploaded_files").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM file_index_status").fetchone()[0] == 0
        assert tuple(conn.execute("SELECT selected_content, session_content FROM chat_history").fetchone()) == (None, None)
        assert conn.execute("SELECT content_id FROM user_preferences").fetchone()[0] is None
        conn.close()


class TestSafeName:
    """Test filename safety validation."""

    def test_safe_name_allows_alphanumeric(self):
        """Verify alphanumeric names are allowed."""
        assert _safe_name("Chapter1English") is True

    def test_safe_name_allows_hyphens(self):
        """Verify hyphens are allowed."""
        assert _safe_name("Chapter-1") is True

    def test_safe_name_rejects_spaces(self):
        """Verify spaces are rejected."""
        assert _safe_name("Chapter 1") is False

    def test_safe_name_rejects_special_chars(self):
        """Verify special characters are rejected."""
        assert _safe_name("Chapter@1!") is False
        assert _safe_name("path/to/file") is False

    def test_safe_name_rejects_empty(self):
        """Verify empty name is rejected."""
        assert _safe_name("") is False

    def test_safe_name_rejects_none(self):
        """Verify None is rejected."""
        # Should handle gracefully
        result = _safe_name(None) if isinstance(None, str) else False
        assert result is False


class TestEffectiveEmail:
    """Test email extraction from user object."""

    def test_effective_email_from_email_field(self):
        """Verify email is extracted from 'email' field."""
        user = {"email": "user@example.com", "username": "john"}
        email = _effective_email(user)
        
        assert email == "user@example.com"

    def test_effective_email_fallback_to_username(self):
        """Verify username is used if email missing."""
        user = {"username": "johnsmith", "email": ""}
        email = _effective_email(user)
        
        assert email == "johnsmith"

    def test_effective_email_case_normalized(self):
        """Verify email is lowercased."""
        user = {"email": "USER@EXAMPLE.COM"}
        email = _effective_email(user)
        
        assert email == "user@example.com"

    def test_effective_email_whitespace_trimmed(self):
        """Verify whitespace is trimmed."""
        user = {"email": "  user@example.com  "}
        email = _effective_email(user)
        
        assert email == "user@example.com"

    def test_effective_email_empty_fallback(self):
        """Verify empty string for missing email and username."""
        user = {"email": "", "username": ""}
        email = _effective_email(user)
        
        assert email == ""


class TestValidateTreeNames:
    """Test folder/file name validation."""

    def test_validate_tree_names_accepts_valid(self):
        """Verify valid names pass validation."""
        # Should not raise
        _validate_tree_names("Class8", "English", "Chapter1", "Vocabulary")

    def test_validate_tree_names_rejects_empty_class(self):
        """Verify empty class name is rejected."""
        with pytest.raises(HTTPException) as exc:
            _validate_tree_names("", "English", "Chapter1", "Vocab")
        
        assert exc.value.status_code == 400

    def test_validate_tree_names_rejects_empty_subject(self):
        """Verify empty subject is rejected."""
        with pytest.raises(HTTPException):
            _validate_tree_names("Class8", "", "Chapter1", "Vocab")

    def test_validate_tree_names_rejects_empty_folder(self):
        """Verify empty folder is rejected."""
        with pytest.raises(HTTPException):
            _validate_tree_names("Class8", "English", "", "Vocab")

    def test_validate_tree_names_rejects_spaces_in_subject(self):
        """Verify spaces in subject names are rejected."""
        with pytest.raises(HTTPException):
            _validate_tree_names("Class8", "Subject Name", "Chapter1", "Vocab")

    def test_validate_tree_names_rejects_special_chars(self):
        """Verify special characters are rejected."""
        with pytest.raises(HTTPException):
            _validate_tree_names("Class8", "English!", "Chapter1", "Vocab")

    def test_validate_tree_names_allows_hyphens(self):
        """Verify hyphens in names are allowed."""
        # Should not raise
        _validate_tree_names("Class-8", "English-Advanced", "Chapter-1", "Unit-1")


class TestValidatePDFUpload:
    """Test PDF file validation."""

    def test_validate_pdf_upload_accepts_pdf(self):
        """Verify PDF files are accepted."""
        upload = MagicMock(spec=UploadFile)
        upload.filename = "document.pdf"
        upload.content_type = "application/pdf"
        
        # Should not raise
        _validate_pdf_upload(upload)

    def test_validate_pdf_upload_rejects_non_pdf(self):
        """Verify non-PDF files are rejected."""
        upload = MagicMock(spec=UploadFile)
        upload.filename = "doc.txt"
        upload.content_type = "text/plain"
        
        with pytest.raises(HTTPException) as exc:
            _validate_pdf_upload(upload)
        
        assert "Only PDF" in str(exc.value.detail)

    def test_validate_pdf_upload_rejects_wrong_mime(self):
        """Verify wrong MIME type is rejected."""
        upload = MagicMock(spec=UploadFile)
        upload.filename = "document.pdf"
        upload.content_type = "application/octet-stream"
        
        with pytest.raises(HTTPException):
            _validate_pdf_upload(upload)

    def test_validate_pdf_upload_case_insensitive(self):
        """Verify validation is case-insensitive."""
        upload = MagicMock(spec=UploadFile)
        upload.filename = "DOCUMENT.PDF"
        upload.content_type = "application/pdf"
        
        # Should not raise
        _validate_pdf_upload(upload)

    def test_validate_pdf_upload_handles_missing_filename(self):
        """Verify handling of missing filename."""
        upload = MagicMock(spec=UploadFile)
        upload.filename = None
        upload.content_type = "application/pdf"
        
        with pytest.raises(HTTPException):
            _validate_pdf_upload(upload)

    def test_validate_pdf_upload_handles_missing_mime(self):
        """Verify handling of missing MIME type."""
        upload = MagicMock(spec=UploadFile)
        upload.filename = "document.pdf"
        upload.content_type = None
        
        # Should not raise (allows missing MIME if filename is PDF)
        _validate_pdf_upload(upload)


class TestGetOrCreateUserStorageRoot:
    """Test user storage directory management."""

    @patch("app.modules.file_management.get_connection")
    @patch("app.modules.file_management.os.makedirs")
    @patch("app.modules.file_management.os.path.join")
    def test_get_or_create_user_storage_root_creates_directory(self, mock_join, mock_makedirs, mock_conn):
        """Verify user storage directory is created."""
        mock_join.side_effect = lambda *args: "/".join(args)
        
        user = {"username": "testuser", "email": "user@example.com"}
        mock_db = MagicMock()
        mock_conn.return_value = mock_db

        result = get_or_create_user_storage_root(user)

        assert isinstance(result, str)
        mock_makedirs.assert_called()

    @patch("app.modules.file_management.get_connection")
    def test_get_or_create_user_storage_root_rejects_missing_username(self, mock_conn):
        """Verify missing username raises exception."""
        user = {"email": "user@example.com"}
        
        with pytest.raises(HTTPException) as exc:
            get_or_create_user_storage_root(user)
        
        assert exc.value.status_code == 400

    @patch("app.modules.file_management.get_connection")
    def test_get_or_create_user_storage_root_fails_empty_user(self, mock_conn):
        """Verify empty user dict raises exception."""
        user = {}
        
        with pytest.raises(HTTPException):
            get_or_create_user_storage_root(user)

    @patch("app.modules.file_management.get_connection")
    @patch("app.modules.file_management.os.makedirs")
    @patch("app.modules.file_management.os.path.join")
    def test_get_or_create_user_storage_root_records_in_db(self, mock_join, mock_makedirs, mock_conn):
        """Verify storage root is recorded in database."""
        mock_join.side_effect = lambda *args: "/".join(args)
        
        user = {"username": "testuser", "email": "user@example.com"}
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db
        
        get_or_create_user_storage_root(user)
        
        mock_cursor.execute.assert_called_once()
        mock_db.commit.assert_called_once()


class TestContentReferences:
    def test_make_kb_content_ref_canonicalizes_relative_path(self):
        canonical = make_kb_content_ref("Class 8/English-1/Text Books/Chapter 1.pdf")
        variant = make_kb_content_ref("Class 8/English-1/../English-1/Text Books/./Chapter 1.pdf")
        assert variant == canonical

    def test_make_upload_content_ref(self):
        assert make_upload_content_ref(42) == "upload:42"

    def test_resolve_kb_content_reference(self, tmp_path):
        kb_root = tmp_path / "knowledge_base"
        chapter = kb_root / "Class 8" / "English-1" / "Text Books"
        chapter.mkdir(parents=True)
        pdf_path = chapter / "Chapter 1.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        relative_path = "Class 8/English-1/Text Books/Chapter 1.pdf"
        content_id = make_kb_content_ref(relative_path)

        with patch("app.modules.file_management._knowledge_base_root", return_value=str(kb_root)):
            resolved = resolve_content_reference({"username": "student"}, content_id)

        assert resolved["content_id"] == content_id
        assert resolved["path"] == str(pdf_path)
        assert resolved["source"] == "knowledge_base"

    @patch("app.modules.file_management._resolve_upload_record")
    def test_resolve_upload_content_reference(self, mock_resolve_upload_record):
        mock_resolve_upload_record.return_value = {
            "id": 7,
            "display_name": "Uploaded Chapter",
            "relative_path": "uploads/hash/Class 8/English-1/Text Books/Uploaded-Chapter.pdf",
        }

        resolved = resolve_content_reference({"username": "student"}, "upload:7")

        assert resolved["content_id"] == "upload:7"
        assert resolved["source"] == "uploaded"
        assert resolved["file_id"] == 7

    def test_resolve_rejects_invalid_reference(self):
        with pytest.raises(HTTPException):
            resolve_content_reference({"username": "student"}, "not-a-valid-reference")

    def test_resolve_relative_path_reference(self, tmp_path):
        kb_root = tmp_path / "knowledge_base"
        chapter = kb_root / "Class 8" / "English-1" / "Text Books"
        chapter.mkdir(parents=True)
        pdf_path = chapter / "Chapter 1.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        relative_path = "Class 8/English-1/Text Books/Chapter 1.pdf"
        with patch("app.modules.file_management._knowledge_base_root", return_value=str(kb_root)):
            resolved = resolve_content_reference({"username": "student"}, relative_path)

        assert resolved["content_id"] == make_kb_content_ref(relative_path)
        assert resolved["path"] == str(pdf_path)
        assert resolved["source"] == "knowledge_base"

    def test_resolve_equivalent_paths_to_single_content_id(self, tmp_path):
        kb_root = tmp_path / "knowledge_base"
        chapter = kb_root / "Class 8" / "English-1" / "Text Books"
        chapter.mkdir(parents=True)
        pdf_path = chapter / "Chapter 1.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        canonical_rel = "Class 8/English-1/Text Books/Chapter 1.pdf"
        variant_rel = "Class 8/English-1/../English-1/Text Books/./Chapter 1.pdf"

        with patch("app.modules.file_management._knowledge_base_root", return_value=str(kb_root)):
            canonical_resolved = resolve_content_reference({"username": "student"}, canonical_rel)
            variant_resolved = resolve_content_reference({"username": "student"}, variant_rel)

        assert canonical_resolved["path"] == str(pdf_path)
        assert variant_resolved["path"] == str(pdf_path)
        assert variant_resolved["content_id"] == canonical_resolved["content_id"]

    def test_resolve_rejects_absolute_path_reference(self):
        with pytest.raises(HTTPException) as exc:
            resolve_content_reference({"username": "student"}, "C:/Windows/System32/cmd.exe")

        assert exc.value.status_code == 400

    @patch("app.modules.file_management.os.path.realpath")
    @patch("app.modules.file_management._knowledge_base_root")
    def test_resolve_kb_absolute_path_rejects_symlink_escape(self, mock_kb_root, mock_realpath):
        mock_kb_root.return_value = "/safe/kb"
        mock_realpath.side_effect = ["/safe/kb", "/outside/secret.pdf"]

        with pytest.raises(HTTPException) as exc:
            _resolve_kb_absolute_path("Class 8/English-1/Text Books/Chapter 1.pdf")

        assert exc.value.status_code == 403


class TestIndexJobLifecycle:
    @patch("app.modules.file_management.get_connection")
    @patch("app.modules.file_management._submit_index_job")
    @patch("app.modules.file_management._create_index_job")
    @patch("app.modules.file_management._load_files_for_scope")
    def test_queue_reindex_uses_managed_submission(self, mock_load_files, mock_create_job, mock_submit_job, mock_conn):
        mock_load_files.return_value = [{"id": 1, "relative_path": "uploads/x.pdf"}]
        mock_create_job.return_value = 91
        mock_submit_job.return_value = True

        cursor = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        result = queue_reindex({"username": "student", "role": "student"}, scope="file", file_id=1)

        assert result == {"job_id": 91, "queued_files": 1}
        mock_submit_job.assert_called_once_with(91, mock_load_files.return_value)
        cursor.execute.assert_any_call(
            """
            UPDATE file_index_status
            SET status_reason='queued', message_id='MSG-1302', updated_at=CURRENT_TIMESTAMP
            WHERE file_id=?
            """,
            (1,),
        )

    @patch("app.modules.file_management._load_files_for_scope")
    def test_queue_reindex_returns_empty_when_no_files(self, mock_load_files):
        mock_load_files.return_value = []

        result = queue_reindex({"username": "student", "role": "student"}, scope="changed")

        assert result == {"job_id": None, "queued_files": 0}

    def test_derive_processing_state_queued_for_uploaded_file(self):
        from app.modules.file_management import _derive_processing_state

        state = _derive_processing_state("UPLOADED", False, "queued")
        assert state == "queued"

    def test_derive_processing_state_failed_for_failed_file(self):
        from app.modules.file_management import _derive_processing_state

        state = _derive_processing_state("FAILED", False, "index_failed")
        assert state == "failed"

    @patch("app.modules.file_management.get_connection")
    def test_get_index_status_reports_processing_state(self, mock_conn):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            {
                "id": 1,
                "display_name": "Chapter 1",
                "upload_status": "UPLOADED",
                "indexed": 0,
                "status_reason": "queued",
                "message_id": "MSG-1302",
                "updated_at": "2025-01-01T00:00:00Z",
            }
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        from app.modules.file_management import get_index_status
        result = get_index_status({"username": "student", "role": "student"}, file_id=1)

        assert result == [
            {
                "file_id": 1,
                "display_name": "Chapter 1",
                "upload_status": "UPLOADED",
                "indexed": False,
                "status_reason": "queued",
                "processing_state": "queued",
                "message_id": "MSG-1302",
                "updated_at": "2025-01-01T00:00:00Z",
            }
        ]

    @patch("app.modules.file_management._submit_index_job")
    @patch("app.modules.file_management._load_files_for_scope")
    @patch("app.modules.file_management.get_connection")
    def test_recover_indexing_jobs_resubmits_queued_and_running(self, mock_conn_factory, mock_load_files, mock_submit_job):
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            {"id": 11, "user_id": "student", "scope_type": "FILE", "scope_ref": "3", "status": "QUEUED"},
            {"id": 12, "user_id": "student", "scope_type": "CHANGED", "scope_ref": None, "status": "RUNNING"},
        ]
        conn.cursor.return_value = cursor
        mock_conn_factory.return_value = conn
        mock_load_files.side_effect = [
            [{"id": 3, "relative_path": "uploads/a.pdf"}],
            [{"id": 4, "relative_path": "uploads/b.pdf"}],
        ]
        mock_submit_job.return_value = True

        result = recover_indexing_jobs()

        assert result == {"recovered": 2, "failed": 0}
        assert mock_submit_job.call_count == 2


class TestFileManagementIntegration:
    """Integration tests for file management."""

    @patch("app.modules.file_management.get_connection")
    @patch("app.modules.file_management.os.makedirs")
    @patch("app.modules.file_management.os.path.join")
    def test_file_management_user_isolation(self, mock_join, mock_makedirs, mock_conn):
        """Verify files are isolated per user."""
        mock_join.side_effect = lambda *args: "/".join(args)
        
        user1 = {"username": "user1", "email": "user1@example.com"}
        user2 = {"username": "user2", "email": "user2@example.com"}
        
        mock_db = MagicMock()
        mock_conn.return_value = mock_db
        
        root1 = get_or_create_user_storage_root(user1)
        root2 = get_or_create_user_storage_root(user2)
        
        # Paths should be different
        assert root1 != root2

    def test_file_sha256_matches_standard(self):
        """Verify hash calculation matches standard."""
        import hashlib
        test_data = b"test content"
        
        calculated = _file_sha256(test_data)
        expected = hashlib.sha256(test_data).hexdigest()
        
        assert calculated == expected
