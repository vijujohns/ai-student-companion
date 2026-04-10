"""Summary note persistence helpers built on top of learning_artifacts."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .db import get_connection

NOTE_ARTIFACT_TYPE = "SUMMARY_NOTE"
DEFAULT_NOTE_TITLE = "Study Note"


def _clean_text(value: Optional[str]) -> str:
    return str(value or "").strip()


def _derive_title(title: Optional[str], content: Optional[str]) -> str:
    explicit = _clean_text(title)
    if explicit:
        return explicit[:200]

    text = _clean_text(content)
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip("📘📒📝 ").strip()
        if stripped:
            return stripped[:200]

    return DEFAULT_NOTE_TITLE


def _decode_payload(raw_payload: Any) -> Dict[str, Any]:
    if isinstance(raw_payload, dict):
        return raw_payload
    try:
        return json.loads(raw_payload or "{}")
    except Exception:
        return {}


def _row_to_note(row) -> Dict[str, Any]:
    payload = _decode_payload(row["payload_json"])
    return {
        "id": int(row["id"]),
        "title": _derive_title(row["title"], payload.get("content")),
        "content": _clean_text(payload.get("content")),
        "source_query": _clean_text(payload.get("source_query")),
        "summary_topic": _clean_text(payload.get("summary_topic")),
        "session_id": row["session_id"],
        "selected_content": row["selected_content"] or payload.get("selected_content"),
        "is_pinned": bool(payload.get("is_pinned", False)),
        "tags": [str(item).strip() for item in (payload.get("tags") or []) if str(item).strip()],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def save_note(
    user_id: str,
    *,
    title: Optional[str],
    content: str,
    session_id: Optional[str] = None,
    source_query: Optional[str] = None,
    selected_content: Optional[str] = None,
    is_pinned: bool = False,
) -> Dict[str, Any]:
    normalized_content = _clean_text(content)
    if not normalized_content:
        raise ValueError("Note content is required")

    normalized_title = _derive_title(title, normalized_content)
    payload = {
        "content": normalized_content,
        "source_query": _clean_text(source_query),
        "selected_content": selected_content,
        "summary_topic": normalized_title,
        "is_pinned": bool(is_pinned),
        "tags": ["notes", "summary"],
    }

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO learning_artifacts
            (user_id, session_id, lesson_plan_id, card_id, artifact_type, title, tags, payload_json, selected_content, created_at, updated_at)
            VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                session_id,
                NOTE_ARTIFACT_TYPE,
                normalized_title,
                "notes,summary",
                json.dumps(payload),
                selected_content,
            ),
        )
        note_id = int(cursor.lastrowid)
        conn.commit()
    finally:
        conn.close()

    note = get_note(user_id, note_id)
    if note is None:
        raise ValueError("Failed to save note")
    return note


def list_notes(user_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, session_id, title, tags, payload_json, created_at, updated_at, selected_content
            FROM learning_artifacts
            WHERE user_id = ? AND artifact_type = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id, NOTE_ARTIFACT_TYPE),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    notes = [_row_to_note(row) for row in rows]
    return sorted(notes, key=lambda item: (item.get("is_pinned", False), item.get("updated_at") or "", item.get("id", 0)), reverse=True)


def get_note(user_id: str, note_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, session_id, title, tags, payload_json, created_at, updated_at, selected_content
            FROM learning_artifacts
            WHERE user_id = ? AND id = ? AND artifact_type = ?
            LIMIT 1
            """,
            (user_id, note_id, NOTE_ARTIFACT_TYPE),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        return None
    return _row_to_note(row)


def update_note(
    user_id: str,
    note_id: int,
    *,
    title: Optional[str] = None,
    content: Optional[str] = None,
    source_query: Optional[str] = None,
    selected_content: Optional[str] = None,
    is_pinned: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    existing = get_note(user_id, note_id)
    if not existing:
        return None

    merged_content = _clean_text(content) or existing["content"]
    merged_title = _derive_title(title or existing["title"], merged_content)
    merged_query = _clean_text(source_query) or existing.get("source_query", "")
    merged_selected_content = selected_content if selected_content is not None else existing.get("selected_content")
    merged_pinned = existing.get("is_pinned", False) if is_pinned is None else bool(is_pinned)

    payload = {
        "content": merged_content,
        "source_query": merged_query,
        "selected_content": merged_selected_content,
        "summary_topic": merged_title,
        "is_pinned": merged_pinned,
        "tags": existing.get("tags") or ["notes", "summary"],
    }

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE learning_artifacts
            SET title = ?, tags = ?, payload_json = ?, selected_content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND id = ? AND artifact_type = ?
            """,
            (
                merged_title,
                "notes,summary",
                json.dumps(payload),
                merged_selected_content,
                user_id,
                note_id,
                NOTE_ARTIFACT_TYPE,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return get_note(user_id, note_id)


def delete_note(user_id: str, note_id: int) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM learning_artifacts WHERE user_id = ? AND id = ? AND artifact_type = ?",
            (user_id, note_id, NOTE_ARTIFACT_TYPE),
        )
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()
