import json
from fastapi import HTTPException
from ..modules.adapters import get_default_service_registry
from ..modules.messages import get_message
from ..modules.policy import consume_quota

services = get_default_service_registry()

DEFAULT_REMINDER_SETTINGS = {
    "enabled": True,
    "frequency": "daily",
    "muted_ids": [],
}


def _consume_quota_or_raise(user: dict, action: str) -> None:
    allowed, message_id = consume_quota(user.get("username", ""), action)
    if allowed:
        return

    msg = get_message(message_id)
    raise HTTPException(
        status_code=429,
        detail={
            "message_id": msg["message_id"],
            "level": msg["level"],
            "message": msg["user_text"],
        },
    )


def _log_progress_activity_safe(
    user: dict,
    activity_type: str,
    *,
    subject: str = "",
    chapter: str = "",
    duration_seconds: int = 0,
) -> None:
    try:
        services.progress.log_activity(
            user_id=user.get("username", ""),
            activity_type=activity_type,
            subject=subject or "",
            chapter=chapter or "",
            duration_seconds=max(0, int(duration_seconds or 0)),
        )
    except Exception:
        pass


def _normalize_reminder_settings(raw_settings) -> dict:
    if isinstance(raw_settings, str):
        try:
            raw_settings = json.loads(raw_settings or "{}")
        except json.JSONDecodeError:
            raw_settings = {}

    if not isinstance(raw_settings, dict):
        raw_settings = {}

    muted_ids = raw_settings.get("muted_ids") or []
    if not isinstance(muted_ids, list):
        muted_ids = []

    frequency = str(raw_settings.get("frequency") or DEFAULT_REMINDER_SETTINGS["frequency"]).strip().lower()
    if frequency not in {"all", "daily", "important-only", "weekly", "off"}:
        frequency = DEFAULT_REMINDER_SETTINGS["frequency"]

    return {
        "enabled": bool(raw_settings.get("enabled", DEFAULT_REMINDER_SETTINGS["enabled"])),
        "frequency": frequency,
        "muted_ids": [str(item).strip() for item in muted_ids if str(item).strip()][:25],
    }


def _assert_session_owner_if_exists(session_id: str, username: str) -> None:
    from ..modules.db import get_connection

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM chat_history WHERE session_id = ? LIMIT 1",
            (session_id,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if row and row[0] != username:
        raise HTTPException(status_code=403, detail="You do not have access to this session")
