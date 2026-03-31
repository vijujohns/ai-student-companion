"""File upload, user isolation, indexing status, and scoped reindex helpers."""

import base64
import binascii
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
import re
import threading
from datetime import datetime, UTC
from typing import Dict, List, Optional

from fastapi import HTTPException, UploadFile

from .db import BASE_DIR, get_connection

ALLOWED_NAME_RE = re.compile(r"^[A-Za-z0-9-]+$")
ALLOWED_MIME_TYPES = {"application/pdf", "application/x-pdf"}
CONTENT_REF_KB_PREFIX = "kb:"
CONTENT_REF_UPLOAD_PREFIX = "upload:"
INDEX_JOB_WORKERS = max(1, int(os.getenv("INDEX_JOB_WORKERS", "2")))
_INDEX_JOB_EXECUTOR = ThreadPoolExecutor(max_workers=INDEX_JOB_WORKERS, thread_name_prefix="indexing-job")
_ACTIVE_JOB_IDS: set[int] = set()
_ACTIVE_JOB_LOCK = threading.Lock()


def _storage_base_dir() -> str:
    path = os.path.join(BASE_DIR, "app", "uploads")
    os.makedirs(path, exist_ok=True)
    return path


def get_uploads_root() -> str:
    """Public accessor for the canonical uploads root."""
    return _storage_base_dir()


def _knowledge_base_root() -> str:
    return os.path.join(BASE_DIR, "knowledge_base")


def _normalize_relative_path(path: str) -> str:
    return str(path or "").replace("\\", "/").strip("/")


def _encode_content_value(value: str) -> str:
    raw = value.encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_content_value(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(f"{value}{padding}").decode("utf-8")
    except (ValueError, UnicodeDecodeError, binascii.Error):
        raise HTTPException(status_code=400, detail="Invalid content reference")


def make_kb_content_ref(relative_path: str) -> str:
    normalized = _normalize_relative_path(relative_path)
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid content reference")
    return f"{CONTENT_REF_KB_PREFIX}{_encode_content_value(normalized)}"


def make_upload_content_ref(file_id: int) -> str:
    return f"{CONTENT_REF_UPLOAD_PREFIX}{int(file_id)}"


def _resolve_kb_absolute_path(relative_path: str) -> str:
    kb_root = os.path.abspath(_knowledge_base_root())
    candidate = os.path.abspath(os.path.join(kb_root, _normalize_relative_path(relative_path)))
    if not candidate.startswith(kb_root + os.sep) and candidate != kb_root:
        raise HTTPException(status_code=403, detail="Access denied")
    return candidate


def _resolve_upload_record(requested_by: Dict[str, str], file_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    if requested_by.get("role") == "admin":
        cursor.execute(
            "SELECT id, user_id, display_name, relative_path FROM uploaded_files WHERE id=? LIMIT 1",
            (file_id,),
        )
    else:
        cursor.execute(
            "SELECT id, user_id, display_name, relative_path FROM uploaded_files WHERE id=? AND user_id=? LIMIT 1",
            (file_id, requested_by.get("username")),
        )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=403, detail="Access denied")
    return dict(row)


def resolve_content_reference(requested_by: Dict[str, str], content_ref: str | None) -> Optional[Dict[str, object]]:
    if not content_ref:
        return None

    reference = str(content_ref).strip()
    if not reference:
        return None

    if reference.startswith(CONTENT_REF_KB_PREFIX):
        relative_path = _decode_content_value(reference[len(CONTENT_REF_KB_PREFIX):])
        full_path = _resolve_kb_absolute_path(relative_path)
        return {
            "content_id": make_kb_content_ref(relative_path),
            "path": full_path,
            "source": "knowledge_base",
            "title": os.path.splitext(os.path.basename(full_path))[0],
        }

    if reference.startswith(CONTENT_REF_UPLOAD_PREFIX):
        suffix = reference[len(CONTENT_REF_UPLOAD_PREFIX):]
        if not suffix.isdigit():
            raise HTTPException(status_code=400, detail="Invalid content reference")
        row = _resolve_upload_record(requested_by, int(suffix))
        return {
            "content_id": make_upload_content_ref(int(row["id"])),
            "path": os.path.join(BASE_DIR, row["relative_path"]),
            "source": "uploaded",
            "title": row.get("display_name") or "Uploaded PDF",
            "file_id": int(row["id"]),
        }

    if os.path.isabs(reference):
        full_path = os.path.abspath(reference)
        kb_root = os.path.abspath(_knowledge_base_root())
        uploads_root = os.path.abspath(get_uploads_root())

        if full_path.startswith(kb_root + os.sep):
            relative_path = os.path.relpath(full_path, kb_root)
            return {
                "content_id": make_kb_content_ref(relative_path),
                "path": full_path,
                "source": "knowledge_base",
                "title": os.path.splitext(os.path.basename(full_path))[0],
            }

        if full_path.startswith(uploads_root + os.sep):
            relative_path = _normalize_relative_path(os.path.relpath(full_path, BASE_DIR))
            conn = get_connection()
            cursor = conn.cursor()
            if requested_by.get("role") == "admin":
                cursor.execute(
                    "SELECT id, display_name, relative_path FROM uploaded_files WHERE relative_path=? LIMIT 1",
                    (relative_path,),
                )
            else:
                cursor.execute(
                    "SELECT id, display_name, relative_path FROM uploaded_files WHERE user_id=? AND relative_path=? LIMIT 1",
                    (requested_by.get("username"), relative_path),
                )
            row = cursor.fetchone()
            conn.close()
            if not row:
                raise HTTPException(status_code=403, detail="Access denied")
            row = dict(row)
            return {
                "content_id": make_upload_content_ref(int(row["id"])),
                "path": os.path.join(BASE_DIR, row["relative_path"]),
                "source": "uploaded",
                "title": row.get("display_name") or "Uploaded PDF",
                "file_id": int(row["id"]),
            }

        raise HTTPException(status_code=403, detail="Access denied")

    raise HTTPException(status_code=400, detail="Invalid content reference")


def _file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_name(name: str) -> bool:
    return bool(name and ALLOWED_NAME_RE.match(name))


def _effective_email(user: Dict[str, str]) -> str:
    email = user.get("email") or user.get("username") or ""
    return str(email).strip().lower()


def get_or_create_user_storage_root(user: Dict[str, str]) -> str:
    user_id = user.get("username") or ""
    email = _effective_email(user)
    if not user_id or not email:
        raise HTTPException(status_code=400, detail={"message_id": "MSG-1404", "message": "User context missing"})

    digest = hashlib.sha256(email.encode("utf-8")).hexdigest()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO user_storage_roots (user_id, email_hash_root)
        VALUES (?, ?)
        """,
        (user_id, digest),
    )
    conn.commit()
    conn.close()

    root = os.path.join(_storage_base_dir(), digest)
    os.makedirs(root, exist_ok=True)
    return root


def _validate_tree_names(class_name: str, subject_name: str, folder_name: str, display_name: str) -> None:
    # Allow broad class names but keep custom folder and file naming strict.
    if not class_name or not subject_name or not folder_name:
        raise HTTPException(status_code=400, detail={"message_id": "MSG-1303", "message": "Class, Subject and Folder are required."})

    for value in (subject_name, folder_name, display_name):
        if not _safe_name(value):
            raise HTTPException(status_code=400, detail={"message_id": "MSG-1303", "message": "Use only letters, numbers, and hyphens."})


def _validate_pdf_upload(upload: UploadFile) -> None:
    file_name = (upload.filename or "").lower()
    content_type = (upload.content_type or "").lower()
    if not file_name.endswith(".pdf"):
        raise HTTPException(status_code=400, detail={"message_id": "MSG-1304", "message": "Only PDF files are supported."})
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail={"message_id": "MSG-1304", "message": "Only PDF files are supported."})


def _insert_upload_record(
    user_id: str,
    class_name: str,
    subject_name: str,
    folder_name: str,
    file_name: str,
    display_name: str,
    relative_path: str,
    mime_type: str,
    size_bytes: int,
    file_sha256: str,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO uploaded_files
        (user_id, class_name, subject_name, folder_name, file_name, display_name, relative_path, mime_type, size_bytes, file_sha256, upload_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'UPLOADED')
        """,
        (
            user_id,
            class_name,
            subject_name,
            folder_name,
            file_name,
            display_name,
            relative_path,
            mime_type,
            size_bytes,
            file_sha256,
        ),
    )
    file_id = int(cursor.lastrowid)
    cursor.execute(
        """
        INSERT OR REPLACE INTO file_index_status
        (file_id, indexed, status_reason, message_id, updated_at)
        VALUES (?, 0, 'queued', 'MSG-1302', CURRENT_TIMESTAMP)
        """,
        (file_id,),
    )
    conn.commit()
    conn.close()
    return file_id


def _create_index_job(user_id: Optional[str], scope_type: str, scope_ref: Optional[str]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO indexing_jobs (user_id, scope_type, scope_ref, status, created_at)
        VALUES (?, ?, ?, 'QUEUED', CURRENT_TIMESTAMP)
        """,
        (user_id, scope_type, scope_ref),
    )
    job_id = int(cursor.lastrowid)
    conn.commit()
    conn.close()
    return job_id


def _set_job_status(job_id: int, status: str, error_code: Optional[str] = None, error_message: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    if status == "RUNNING":
        cursor.execute(
            """
            UPDATE indexing_jobs
            SET status='RUNNING', started_at=?, error_code=NULL, error_message=NULL
            WHERE id=?
            """,
            (datetime.now(UTC).isoformat(), job_id),
        )
    elif status in {"SUCCESS", "FAILED"}:
        cursor.execute(
            """
            UPDATE indexing_jobs
            SET status=?, ended_at=?, error_code=?, error_message=?
            WHERE id=?
            """,
            (status, datetime.now(UTC).isoformat(), error_code, error_message, job_id),
        )
    conn.commit()
    conn.close()


def _set_file_index_status(file_id: int, indexed: bool, reason: str, message_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO file_index_status
        (file_id, indexed, last_indexed_at, status_reason, message_id, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (file_id, 1 if indexed else 0, datetime.now(UTC).isoformat() if indexed else None, reason, message_id),
    )
    cursor.execute(
        """
        UPDATE uploaded_files
        SET upload_status=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        ("INDEXED" if indexed else "FAILED", file_id),
    )
    conn.commit()
    conn.close()


def _run_index_job(job_id: int, file_rows: List[Dict[str, str]]):
    _set_job_status(job_id, "RUNNING")
    from .ingestion import ingest_pdf

    try:
        for row in file_rows:
            file_id = int(row["id"])
            relative_path = row["relative_path"]
            full_path = os.path.join(BASE_DIR, relative_path)
            if not os.path.isfile(full_path):
                _set_file_index_status(file_id, False, "file_missing", "MSG-1404")
                continue
            try:
                ingest_pdf(full_path)
                _set_file_index_status(file_id, True, "indexed", "MSG-1000")
            except Exception:
                _set_file_index_status(file_id, False, "index_failed", "MSG-1302")

        _set_job_status(job_id, "SUCCESS")
    except Exception as exc:
        _set_job_status(job_id, "FAILED", error_code="INDEX_EXCEPTION", error_message=str(exc))


def _submit_index_job(job_id: int, file_rows: List[Dict[str, str]]) -> bool:
    if not file_rows:
        _set_job_status(job_id, "FAILED", error_code="JOB_SCOPE_EMPTY", error_message="No files matched indexing job scope")
        return False

    with _ACTIVE_JOB_LOCK:
        if job_id in _ACTIVE_JOB_IDS:
            return False
        _ACTIVE_JOB_IDS.add(job_id)

    def runner():
        try:
            _run_index_job(job_id, file_rows)
        finally:
            with _ACTIVE_JOB_LOCK:
                _ACTIVE_JOB_IDS.discard(job_id)

    try:
        _INDEX_JOB_EXECUTOR.submit(runner)
        return True
    except Exception as exc:
        with _ACTIVE_JOB_LOCK:
            _ACTIVE_JOB_IDS.discard(job_id)
        _set_job_status(job_id, "FAILED", error_code="JOB_SUBMIT_FAILED", error_message=str(exc))
        raise


def _load_files_for_scope(requested_by: Dict[str, str], scope: str, file_id: Optional[int]) -> List[Dict[str, str]]:
    user_id = requested_by.get("username")
    role = requested_by.get("role", "student")

    conn = get_connection()
    cursor = conn.cursor()

    if scope == "file":
        if not file_id:
            conn.close()
            raise HTTPException(status_code=400, detail={"message_id": "MSG-1404", "message": "file_id is required for file scope"})
        if role == "admin":
            cursor.execute("SELECT * FROM uploaded_files WHERE id=?", (file_id,))
        else:
            cursor.execute("SELECT * FROM uploaded_files WHERE id=? AND user_id=?", (file_id, user_id))
    elif scope == "changed":
        if role == "admin":
            cursor.execute("SELECT * FROM uploaded_files WHERE upload_status IN ('UPLOADED', 'FAILED')")
        else:
            cursor.execute("SELECT * FROM uploaded_files WHERE user_id=? AND upload_status IN ('UPLOADED', 'FAILED')", (user_id,))
    else:  # all
        if role == "admin":
            cursor.execute("SELECT * FROM uploaded_files")
        else:
            cursor.execute("SELECT * FROM uploaded_files WHERE user_id=?", (user_id,))

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def queue_reindex(requested_by: Dict[str, str], scope: str, file_id: Optional[int] = None) -> Dict[str, object]:
    normalized_scope = (scope or "changed").lower()
    if normalized_scope not in {"all", "changed", "file"}:
        raise HTTPException(status_code=400, detail={"message_id": "MSG-1404", "message": "Invalid reindex scope"})

    files = _load_files_for_scope(requested_by, normalized_scope, file_id)
    if not files:
        return {"job_id": None, "queued_files": 0}

    scope_ref = str(file_id) if file_id else None
    job_id = _create_index_job(requested_by.get("username"), normalized_scope.upper(), scope_ref)
    _submit_index_job(job_id, files)

    return {"job_id": job_id, "queued_files": len(files)}


def recover_indexing_jobs() -> Dict[str, int]:
    """Resume queued/running indexing jobs after process restarts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, user_id, scope_type, scope_ref, status
        FROM indexing_jobs
        WHERE status IN ('QUEUED', 'RUNNING')
        ORDER BY created_at ASC, id ASC
        """
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    recovered = 0
    failed = 0

    for row in rows:
        normalized_scope = str(row.get("scope_type") or "changed").strip().lower()
        scope_ref = row.get("scope_ref")
        requested_by = {
            "username": row.get("user_id"),
            "role": "admin" if row.get("user_id") == "admin" else "student",
        }

        try:
            scoped_file_id = int(scope_ref) if normalized_scope == "file" and scope_ref else None
            files = _load_files_for_scope(requested_by, normalized_scope, scoped_file_id)
            if _submit_index_job(int(row["id"]), files):
                recovered += 1
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            _set_job_status(int(row["id"]), "FAILED", error_code="JOB_RECOVERY_FAILED", error_message=str(exc))

    return {"recovered": recovered, "failed": failed}


def upload_pdf(
    user: Dict[str, str],
    upload: UploadFile,
    class_name: str,
    subject_name: str,
    folder_name: str,
    display_name: str,
) -> Dict[str, object]:
    _validate_pdf_upload(upload)
    _validate_tree_names(class_name, subject_name, folder_name, display_name)

    root = get_or_create_user_storage_root(user)
    user_id = user.get("username")

    extension = ".pdf"
    final_file_name = f"{display_name}{extension}"

    destination_dir = os.path.join(root, class_name, subject_name, folder_name)
    os.makedirs(destination_dir, exist_ok=True)

    destination_path = os.path.join(destination_dir, final_file_name)
    content = upload.file.read()
    with open(destination_path, "wb") as fh:
        fh.write(content)

    relative_path = os.path.relpath(destination_path, BASE_DIR)
    file_hash = _file_sha256(content)

    file_id = _insert_upload_record(
        user_id=user_id,
        class_name=class_name,
        subject_name=subject_name,
        folder_name=folder_name,
        file_name=final_file_name,
        display_name=display_name,
        relative_path=relative_path,
        mime_type=upload.content_type or "application/pdf",
        size_bytes=len(content),
        file_sha256=file_hash,
    )

    job_id = _create_index_job(user_id, "FILE", str(file_id))
    _submit_index_job(job_id, [{"id": file_id, "relative_path": relative_path}])

    return {
        "file_id": file_id,
        "job_id": job_id,
        "display_name": display_name,
        "status": "UPLOADED",
        "relative_path": relative_path.replace("\\", "/"),
        "content_id": make_upload_content_ref(file_id),
    }


def get_index_status(user: Dict[str, str], file_id: Optional[int] = None) -> List[Dict[str, object]]:
    conn = get_connection()
    cursor = conn.cursor()

    role = user.get("role", "student")
    user_id = user.get("username")

    if file_id is not None:
        if role == "admin":
            cursor.execute(
                """
                SELECT uf.id, uf.display_name, uf.upload_status, fis.indexed, fis.status_reason, fis.message_id, uf.updated_at
                FROM uploaded_files uf
                LEFT JOIN file_index_status fis ON fis.file_id = uf.id
                WHERE uf.id=?
                """,
                (file_id,),
            )
        else:
            cursor.execute(
                """
                SELECT uf.id, uf.display_name, uf.upload_status, fis.indexed, fis.status_reason, fis.message_id, uf.updated_at
                FROM uploaded_files uf
                LEFT JOIN file_index_status fis ON fis.file_id = uf.id
                WHERE uf.id=? AND uf.user_id=?
                """,
                (file_id, user_id),
            )
    elif role == "admin":
        cursor.execute(
            """
            SELECT uf.id, uf.display_name, uf.upload_status, fis.indexed, fis.status_reason, fis.message_id, uf.updated_at
            FROM uploaded_files uf
            LEFT JOIN file_index_status fis ON fis.file_id = uf.id
            ORDER BY uf.updated_at DESC
            """
        )
    else:
        cursor.execute(
            """
            SELECT uf.id, uf.display_name, uf.upload_status, fis.indexed, fis.status_reason, fis.message_id, uf.updated_at
            FROM uploaded_files uf
            LEFT JOIN file_index_status fis ON fis.file_id = uf.id
            WHERE uf.user_id=?
            ORDER BY uf.updated_at DESC
            """,
            (user_id,),
        )

    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return [
        {
            "file_id": r["id"],
            "display_name": r["display_name"],
            "upload_status": r["upload_status"],
            "indexed": bool(r.get("indexed") or False),
            "status_reason": r.get("status_reason"),
            "message_id": r.get("message_id") or "MSG-1302",
            "updated_at": r.get("updated_at"),
        }
        for r in rows
    ]


def get_files_tree(user: Dict[str, str]) -> List[Dict[str, object]]:
    conn = get_connection()
    cursor = conn.cursor()

    role = user.get("role", "student")
    user_id = user.get("username")

    if role == "admin":
        cursor.execute(
            """
            SELECT uf.class_name, uf.subject_name, uf.folder_name,
                   uf.id, uf.display_name, uf.relative_path,
                   COALESCE(fis.indexed, 0) AS indexed,
                   COALESCE(fis.message_id, 'MSG-1302') AS message_id
            FROM uploaded_files uf
            LEFT JOIN file_index_status fis ON fis.file_id = uf.id
            ORDER BY uf.class_name, uf.subject_name, uf.folder_name, uf.display_name
            """
        )
    else:
        cursor.execute(
            """
            SELECT uf.class_name, uf.subject_name, uf.folder_name,
                   uf.id, uf.display_name, uf.relative_path,
                   COALESCE(fis.indexed, 0) AS indexed,
                   COALESCE(fis.message_id, 'MSG-1302') AS message_id
            FROM uploaded_files uf
            LEFT JOIN file_index_status fis ON fis.file_id = uf.id
            WHERE uf.user_id=?
            ORDER BY uf.class_name, uf.subject_name, uf.folder_name, uf.display_name
            """,
            (user_id,),
        )

    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    tree: Dict[str, Dict[str, Dict[str, List[Dict[str, object]]]]] = {}
    for row in rows:
        cls = row["class_name"]
        subj = row["subject_name"]
        folder = row["folder_name"]
        absolute_path = os.path.join(BASE_DIR, row["relative_path"])
        tree.setdefault(cls, {}).setdefault(subj, {}).setdefault(folder, []).append(
            {
                "file_id": row["id"],
                "title": row["display_name"],
                "content_id": make_upload_content_ref(int(row["id"])),
                "indexed": bool(row["indexed"]),
                "selectable": bool(row["indexed"]),
                "message_id": row["message_id"],
            }
        )

    output = []
    for cls, subjects in tree.items():
        subject_nodes = []
        for subj, folders in subjects.items():
            folder_nodes = []
            for folder, files in folders.items():
                folder_nodes.append({"folder": folder, "files": files})
            subject_nodes.append({"subject": subj, "folders": folder_nodes})
        output.append({"class_name": cls, "subjects": subject_nodes})

    return output
