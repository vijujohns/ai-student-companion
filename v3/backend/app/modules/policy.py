"""Plan policy, usage counters, and quota checks."""

import sqlite3
from datetime import datetime, timedelta, UTC
from typing import Dict, Tuple

from .db import get_connection
from .subscriptions import get_plan_entitlements, list_active_user_classes


FREE_DEFAULT_LIMITS = {
    "uploads_count": 1,
    "quiz_count": 25,
    "flashcard_count": 25,
    "lesson_count": 25,
    "ask_count": 200,
}


PLAN_LIMITS = {
    "free": FREE_DEFAULT_LIMITS,
    "pro": {
        "uploads_count": 100,
        "quiz_count": 1000,
        "flashcard_count": 1000,
        "lesson_count": 1000,
        "ask_count": 5000,
    },
    "premium": {
        "uploads_count": 1000,
        "quiz_count": 20000,
        "flashcard_count": 20000,
        "lesson_count": 20000,
        "ask_count": 100000,
    },
}


_ACTION_FIELD = {
    "upload": "uploads_count",
    "quiz": "quiz_count",
    "flashcard": "flashcard_count",
    "lesson": "lesson_count",
    "ask": "ask_count",
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


# Maps each action field name to its column index in _get_active_period_row results.
# Columns: id=0, period_start=1, period_end=2, uploads_count=3, quiz_count=4,
#          flashcard_count=5, lesson_count=6, ask_count=7
_FIELD_ROW_IDX: dict[str, int] = {
    "uploads_count": 3,
    "quiz_count": 4,
    "flashcard_count": 5,
    "lesson_count": 6,
    "ask_count": 7,
}


def _get_active_period_row(cursor, user_id: str, now_iso: str):
    cursor.execute(
        """
        SELECT id, period_start, period_end, uploads_count, quiz_count, flashcard_count, lesson_count, ask_count
        FROM usage_counters
        WHERE user_id=? AND period_end>?
        ORDER BY period_end DESC, id DESC
        LIMIT 1
        """,
        (user_id, now_iso),
    )
    return cursor.fetchone()


def _ensure_active_period(cursor, user_id: str, now: datetime):
    now_iso = now.isoformat()
    row = _get_active_period_row(cursor, user_id, now_iso)
    if row:
        return row

    period_start = now_iso
    period_end = (now + timedelta(days=7)).isoformat()
    cursor.execute(
        """
        INSERT INTO usage_counters
        (user_id, period_start, period_end)
        VALUES (?, ?, ?)
        """,
        (user_id, period_start, period_end),
    )
    return _get_active_period_row(cursor, user_id, now_iso)


def _row_to_usage(row) -> Dict[str, int]:
    if not row:
        return {
            "uploads_count": 0,
            "quiz_count": 0,
            "flashcard_count": 0,
            "lesson_count": 0,
            "ask_count": 0,
        }

    return {
        "uploads_count": int(row[3]),
        "quiz_count": int(row[4]),
        "flashcard_count": int(row[5]),
        "lesson_count": int(row[6]),
        "ask_count": int(row[7]),
    }


def ensure_user_plan_defaults(user_id: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT plan_code, plan_started_at, trial_ends_at
        FROM users
        WHERE username=?
        LIMIT 1
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return

    plan_code, plan_started_at, trial_ends_at = row
    if plan_code and plan_started_at and trial_ends_at:
        conn.close()
        return

    now = datetime.now(UTC)
    cursor.execute(
        """
        UPDATE users
        SET plan_code=?,
            plan_started_at=COALESCE(plan_started_at, ?),
            trial_ends_at=COALESCE(trial_ends_at, ?),
            is_trial=COALESCE(is_trial, 1)
        WHERE username=?
        """,
        (plan_code or "free", now.isoformat(), (now + timedelta(days=7)).isoformat(), user_id),
    )
    conn.commit()
    conn.close()


def get_user_plan(user_id: str) -> Dict[str, object]:
    ensure_user_plan_defaults(user_id)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT username, plan_code, plan_started_at, plan_expires_at, auto_renew, is_trial, trial_ends_at
        FROM users
        WHERE username=?
        LIMIT 1
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "user_id": user_id,
            "plan_code": "free",
            "limits": PLAN_LIMITS["free"],
            "is_trial": True,
            "trial_ends_at": None,
        }

    plan_code = row[1] or "free"
    return {
        "user_id": row[0],
        "plan_code": plan_code,
        "plan_started_at": row[2],
        "plan_expires_at": row[3],
        "auto_renew": bool(row[4]),
        "is_trial": bool(row[5]),
        "trial_ends_at": row[6],
        "limits": PLAN_LIMITS.get(plan_code, PLAN_LIMITS["free"]),
        "entitlements": get_plan_entitlements(plan_code),
        "classes": list_active_user_classes(row[0]),
    }


def _get_or_create_usage_row(user_id: str) -> Dict[str, int]:
    conn = get_connection()
    cursor = conn.cursor()
    row = _ensure_active_period(cursor, user_id, _utc_now())
    conn.commit()
    conn.close()
    return _row_to_usage(row)


def increment_usage(user_id: str, action: str) -> None:
    field = _ACTION_FIELD.get(action)
    if not field:
        return

    conn = get_connection()
    cursor = conn.cursor()
    row = _ensure_active_period(cursor, user_id, _utc_now())
    if not row:
        conn.close()
        return
    cursor.execute(
        f"""
        UPDATE usage_counters
        SET {field} = COALESCE({field}, 0) + 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (int(row[0]),),
    )
    conn.commit()
    conn.close()


def release_usage(user_id: str, action: str) -> None:
    field = _ACTION_FIELD.get(action)
    if not field:
        return

    conn = get_connection()
    cursor = conn.cursor()
    row = _ensure_active_period(cursor, user_id, _utc_now())
    if row:
        cursor.execute(
            f"""
            UPDATE usage_counters
            SET {field} = CASE WHEN COALESCE({field}, 0) > 0 THEN {field} - 1 ELSE 0 END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (int(row[0]),),
        )
        conn.commit()
    conn.close()


def consume_quota(user_id: str, action: str) -> Tuple[bool, str]:
    field = _ACTION_FIELD.get(action)
    if not field:
        return True, "MSG-1000"

    plan = get_user_plan(user_id)
    limit = int(plan["limits"].get(field, 0))

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        row = _ensure_active_period(cursor, user_id, _utc_now())
        used = int(row[_FIELD_ROW_IDX[field]])
        if limit > 0 and used >= limit:
            conn.rollback()
            return False, "MSG-1201"

        cursor.execute(
            f"""
            UPDATE usage_counters
            SET {field} = COALESCE({field}, 0) + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (int(row[0]),),
        )
        conn.commit()
        return True, "MSG-1000"
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def check_quota(user_id: str, action: str) -> Tuple[bool, str]:
    field = _ACTION_FIELD.get(action)
    if not field:
        return True, "MSG-1000"

    plan = get_user_plan(user_id)
    usage = _get_or_create_usage_row(user_id)
    limit = int(plan["limits"].get(field, 0))
    used = int(usage.get(field, 0))

    if limit > 0 and used >= limit:
        return False, "MSG-1201"
    return True, "MSG-1000"


def get_usage_snapshot(user_id: str) -> Dict[str, int]:
    return _get_or_create_usage_row(user_id)
