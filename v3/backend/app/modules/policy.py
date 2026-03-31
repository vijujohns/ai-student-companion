"""Plan policy, usage counters, and quota checks."""

from datetime import datetime, timedelta, UTC
from typing import Dict, Tuple

from .db import get_connection


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


def _current_period() -> Tuple[str, str]:
    now = datetime.now(UTC)
    period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    period_end = period_start + timedelta(days=7)
    return period_start.isoformat(), period_end.isoformat()


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
    }


def _get_or_create_usage_row(user_id: str) -> Dict[str, int]:
    period_start, period_end = _current_period()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO usage_counters
        (user_id, period_start, period_end)
        VALUES (?, ?, ?)
        """,
        (user_id, period_start, period_end),
    )
    conn.commit()
    cursor.execute(
        """
        SELECT uploads_count, quiz_count, flashcard_count, lesson_count, ask_count
        FROM usage_counters
        WHERE user_id=? AND period_start=? AND period_end=?
        LIMIT 1
        """,
        (user_id, period_start, period_end),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "uploads_count": 0,
            "quiz_count": 0,
            "flashcard_count": 0,
            "lesson_count": 0,
            "ask_count": 0,
        }

    return {
        "uploads_count": int(row[0]),
        "quiz_count": int(row[1]),
        "flashcard_count": int(row[2]),
        "lesson_count": int(row[3]),
        "ask_count": int(row[4]),
    }


def increment_usage(user_id: str, action: str) -> None:
    field = _ACTION_FIELD.get(action)
    if not field:
        return

    period_start, period_end = _current_period()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO usage_counters
        (user_id, period_start, period_end)
        VALUES (?, ?, ?)
        """,
        (user_id, period_start, period_end),
    )
    cursor.execute(
        f"""
        UPDATE usage_counters
        SET {field} = COALESCE({field}, 0) + 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id=? AND period_start=? AND period_end=?
        """,
        (user_id, period_start, period_end),
    )
    conn.commit()
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
