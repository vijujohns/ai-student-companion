"""Standard user-facing message envelope helpers."""

from typing import Any, Dict, Optional

from .db import get_connection


def get_message(message_id: str) -> Dict[str, str]:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT message_id, level, user_friendly_text
            FROM message_catalog
            WHERE message_id=?
            LIMIT 1
            """,
            (message_id,),
        )
        row = cursor.fetchone()
        conn.close()
    except Exception:
        row = None

    if not row:
        return {
            "message_id": "MSG-1000",
            "level": "INFO",
            "user_text": "Operation completed successfully.",
        }

    return {
        "message_id": row[0],
        "level": row[1],
        "user_text": row[2],
    }


def envelope(payload: Optional[Dict[str, Any]] = None, message_id: str = "MSG-1000", **extra: Any) -> Dict[str, Any]:
    meta = get_message(message_id)
    body: Dict[str, Any] = payload.copy() if payload else {}
    body["message"] = meta
    if extra:
        body.update(extra)
    return body
