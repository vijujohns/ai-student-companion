"""
Progress Intelligence: learning time tracking, subject mastery scoring,
study streaks, and dashboard analytics.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .db import get_connection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Activity types
# ---------------------------------------------------------------------------
ACTIVITY_CHAT    = "chat"
ACTIVITY_LESSON  = "lesson"
ACTIVITY_QUIZ    = "quiz"
ACTIVITY_FLASHCARD = "flashcard"
ACTIVITY_ASSESSMENT = "assessment"

VALID_ACTIVITIES = {ACTIVITY_CHAT, ACTIVITY_LESSON, ACTIVITY_QUIZ, ACTIVITY_FLASHCARD, ACTIVITY_ASSESSMENT}


def _safe_json_obj(value: Any, fallback: Optional[Dict] = None) -> Dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return fallback or {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else (fallback or {})
    except Exception:
        return fallback or {}


def _get_assessment_summary(cursor, user_id: str) -> Dict:
    """Aggregate scored assessment attempts into a dashboard-friendly snapshot."""
    try:
        cursor.execute(
            "SELECT id, subject, paper_json FROM assessment_papers WHERE user_id=? ORDER BY id DESC",
            (user_id,),
        )
        rows = cursor.fetchall()
    except Exception:
        return {}

    attempt_entries: List[Dict[str, Any]] = []
    fallback_recent: List[int] = []
    fallback_count = 0
    fallback_best = 0
    fallback_latest = 0
    fallback_last_attempted_at = None
    fallback_latest_subject = ""

    for row in rows:
        paper_id = row[0]
        subject = row[1] or ""
        payload = _safe_json_obj(row[2], {})
        attempts = payload.get("attempts") or []

        if isinstance(attempts, list) and attempts:
            for attempt in attempts:
                if not isinstance(attempt, dict):
                    continue
                score = max(0, min(100, int(attempt.get("score_pct") or 0)))
                recorded_at = str(attempt.get("recorded_at") or "")
                attempt_entries.append(
                    {
                        "paper_id": paper_id,
                        "subject": subject or payload.get("subject") or "",
                        "score_pct": score,
                        "recorded_at": recorded_at,
                        "order": len(attempt_entries),
                    }
                )
            continue

        summary = payload.get("attempt_summary") or {}
        if isinstance(summary, dict) and int(summary.get("attempt_count") or 0) > 0:
            fallback_count += int(summary.get("attempt_count") or 0)
            fallback_best = max(fallback_best, int(summary.get("best_score_pct") or 0))
            latest_score = max(0, min(100, int(summary.get("last_score_pct") or 0)))
            last_attempted_at = summary.get("last_attempted_at") or None
            if last_attempted_at and (fallback_last_attempted_at is None or str(last_attempted_at) >= str(fallback_last_attempted_at)):
                fallback_last_attempted_at = last_attempted_at
                fallback_latest = latest_score
                fallback_latest_subject = subject or payload.get("subject") or ""

            if not fallback_recent:
                fallback_recent = [
                    max(0, min(100, int(score or 0)))
                    for score in (summary.get("recent_scores") or [])[:3]
                ]

    if attempt_entries:
        attempt_entries.sort(
            key=lambda item: (str(item.get("recorded_at") or ""), int(item.get("order") or 0)),
            reverse=True,
        )
        scores = [int(entry.get("score_pct") or 0) for entry in attempt_entries]
        latest = attempt_entries[0]
        attempted_assessments = len({int(entry.get("paper_id") or 0) for entry in attempt_entries})
        return {
            "attempt_count": len(attempt_entries),
            "attempted_assessments": attempted_assessments,
            "average_score_pct": int(round(sum(scores) / len(scores))) if scores else 0,
            "best_score_pct": max(scores) if scores else 0,
            "latest_score_pct": int(latest.get("score_pct") or 0),
            "latest_subject": latest.get("subject") or "",
            "last_attempted_at": latest.get("recorded_at") or None,
            "recent_scores": [int(entry.get("score_pct") or 0) for entry in attempt_entries[:3]],
        }

    if fallback_count > 0:
        average_source = fallback_recent or [fallback_latest]
        attempted_assessments = 1 if fallback_count > 0 else 0
        return {
            "attempt_count": fallback_count,
            "attempted_assessments": attempted_assessments,
            "average_score_pct": int(round(sum(average_source) / len(average_source))) if average_source else 0,
            "best_score_pct": fallback_best,
            "latest_score_pct": fallback_latest,
            "latest_subject": fallback_latest_subject,
            "last_attempted_at": fallback_last_attempted_at,
            "recent_scores": fallback_recent,
        }

    return {}


def _get_week_key(offset_weeks: int = 0) -> str:
    current_day = datetime.now(timezone.utc).date() + timedelta(weeks=offset_weeks)
    iso_year, iso_week, _ = current_day.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _parse_due_label_date(due_label: Any) -> Optional[datetime]:
    raw_value = str(due_label or "").strip()
    if not raw_value:
        return None

    candidates = [raw_value]
    if raw_value.endswith("Z"):
        candidates.append(f"{raw_value[:-1]}+00:00")
    if "T" not in raw_value and " " not in raw_value:
        candidates.append(f"{raw_value}T00:00:00+00:00")

    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            continue

    return None


def _list_assignments(cursor, user_id: str) -> List[Dict[str, Any]]:
    try:
        cursor.execute(
            """
            SELECT id, author_user_id, author_role, title, description, action_tab, cta_label, chapter_hint, context_hint, due_label, status, created_at, completed_at
            FROM mentor_assignments
            WHERE student_user_id = ?
            ORDER BY CASE WHEN status = 'assigned' THEN 0 ELSE 1 END, created_at DESC, id DESC
            LIMIT 8
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
    except Exception:
        return []

    return [
        {
            "id": row[0],
            "author_user_id": row[1],
            "author_role": row[2],
            "title": row[3],
            "description": row[4],
            "action_tab": row[5],
            "cta_label": row[6],
            "chapter_hint": row[7],
            "context_hint": row[8],
            "due_label": row[9],
            "status": row[10],
            "created_at": row[11],
            "completed_at": row[12],
        }
        for row in rows
    ]


def _load_study_plan_overrides(user_id: str, week_key: Optional[str] = None) -> Dict[str, bool]:
    current_week = week_key or _get_week_key()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT item_type, item_id, completed
            FROM study_plan_progress
            WHERE user_id = ? AND week_key = ?
            """,
            (user_id, current_week),
        )
        rows = cursor.fetchall()
    except Exception:
        return {}
    finally:
        conn.close()

    return {
        f"{str(row[0] or 'schedule').strip().lower()}::{str(row[1] or '').strip()}": bool(row[2])
        for row in rows
        if row and str(row[1] or '').strip()
    }


def save_study_plan_item_state(user_id: str, item_id: str, item_type: str, completed: bool) -> Dict[str, Any]:
    week_key = _get_week_key()
    normalized_item_type = (item_type or "schedule").strip().lower()
    if normalized_item_type not in {"schedule", "goal"}:
        normalized_item_type = "schedule"

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO study_plan_progress (user_id, week_key, item_id, item_type, completed, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, week_key, item_id, item_type)
            DO UPDATE SET completed = excluded.completed, updated_at = excluded.updated_at
            """,
            (
                user_id,
                week_key,
                item_id,
                normalized_item_type,
                1 if completed else 0,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "status": "saved",
        "item_id": item_id,
        "item_type": normalized_item_type,
        "completed": bool(completed),
        "week_key": week_key,
    }


def _summarize_plan_history_payload(payload: Dict[str, Any], week_key: str) -> Dict[str, Any]:
    schedule = payload.get("schedule") or []
    targets = payload.get("targets") or []
    return {
        "week_key": week_key,
        "headline": payload.get("headline") or "",
        "focus_subject": payload.get("focus_subject") or "General",
        "completed_steps": sum(1 for step in schedule if step.get("completed")),
        "total_steps": len(schedule),
        "goal_completed": sum(1 for target in targets if target.get("completed")),
        "goal_total": len(targets),
    }


def _build_history_summary(current_summary: Dict[str, Any], previous_summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not previous_summary:
        return {
            "step_delta": int(current_summary.get("completed_steps") or 0),
            "goal_delta": int(current_summary.get("goal_completed") or 0),
            "summary": "This week’s plan is now being tracked for future comparisons.",
        }

    step_delta = int(current_summary.get("completed_steps") or 0) - int(previous_summary.get("completed_steps") or 0)
    goal_delta = int(current_summary.get("goal_completed") or 0) - int(previous_summary.get("goal_completed") or 0)
    direction = "up" if goal_delta >= 0 else "down"
    return {
        "step_delta": step_delta,
        "goal_delta": goal_delta,
        "summary": f"{direction.title()} {abs(goal_delta)} goal{'s' if abs(goal_delta) != 1 else ''} from last week.",
    }


def _save_study_plan_snapshot(user_id: str, week_key: str, payload: Dict[str, Any]) -> None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT INTO study_plan_snapshots (user_id, week_key, plan_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, week_key)
            DO UPDATE SET plan_json = excluded.plan_json, updated_at = excluded.updated_at
            """,
            (user_id, week_key, json.dumps(payload), now_iso, now_iso),
        )
        conn.commit()
    finally:
        conn.close()


def _load_study_plan_history(user_id: str, current_week_key: str, current_payload: Dict[str, Any]) -> Dict[str, Any]:
    current_summary = _summarize_plan_history_payload(current_payload, current_week_key)
    previous_summary = None

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT week_key, plan_json
            FROM study_plan_snapshots
            WHERE user_id = ? AND week_key <> ?
            ORDER BY week_key DESC
            LIMIT 1
            """,
            (user_id, current_week_key),
        )
        row = cursor.fetchone()
    except Exception:
        row = None
    finally:
        conn.close()

    if row:
        previous_week_key = str(row[0] or "")
        previous_payload = _safe_json_obj(row[1], {})
        previous_summary = _summarize_plan_history_payload(previous_payload, previous_week_key)

    return {
        "current_week": current_summary,
        "previous_week": previous_summary,
        "comparison": _build_history_summary(current_summary, previous_summary),
    }

# ---------------------------------------------------------------------------
# Time logging
# ---------------------------------------------------------------------------

def log_activity(
    user_id: str,
    activity_type: str,
    subject: str = "",
    chapter: str = "",
    duration_seconds: int = 0,
) -> int:
    """Record a study activity event. Returns the new row id."""
    if activity_type not in VALID_ACTIVITIES:
        activity_type = "other"
    duration_seconds = max(0, int(duration_seconds or 0))
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO learning_time_log (user_id, activity_type, subject, chapter, duration_seconds)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, activity_type, subject or "", chapter or "", duration_seconds),
        )
        row_id = cursor.lastrowid
        conn.commit()
        return row_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Mastery scoring
# ---------------------------------------------------------------------------

def update_mastery(
    user_id: str,
    subject: str,
    chapter: str,
    correct: int,
    total: int,
) -> float:
    """
    Update rolling mastery for a user+subject+chapter after a quiz.

    Rolling formula: new_mastery = old * 0.6 + latest_score * 0.4
    First attempt: mastery = latest_score.
    Returns the updated mastery_pct.
    """
    if total <= 0:
        return 0.0
    latest_score = round((correct / total) * 100, 1)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT mastery_pct, quizzes_taken FROM mastery_scores "
            "WHERE user_id=? AND subject=? AND chapter=? LIMIT 1",
            (user_id, subject or "", chapter or ""),
        )
        row = cursor.fetchone()

        if row is None:
            new_mastery = latest_score
            new_count = 1
            cursor.execute(
                """
                INSERT INTO mastery_scores (user_id, subject, chapter, mastery_pct, quizzes_taken, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, subject or "", chapter or "", new_mastery, new_count, datetime.now(timezone.utc).isoformat()),
            )
        else:
            old_mastery, quizzes_taken = row[0], row[1]
            new_mastery = round(old_mastery * 0.6 + latest_score * 0.4, 1)
            new_count = (quizzes_taken or 0) + 1
            cursor.execute(
                """
                UPDATE mastery_scores
                SET mastery_pct=?, quizzes_taken=?, last_updated=?
                WHERE user_id=? AND subject=? AND chapter=?
                """,
                (new_mastery, new_count, datetime.now(timezone.utc).isoformat(), user_id, subject or "", chapter or ""),
            )

        conn.commit()
        return new_mastery
    finally:
        conn.close()


def get_mastery_stats(user_id: str) -> List[Dict]:
    """
    Return mastery scores for a user, grouped by subject.

    Each entry: {subject, chapter, mastery_pct, quizzes_taken, last_updated}
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT subject, chapter, mastery_pct, quizzes_taken, last_updated
            FROM mastery_scores
            WHERE user_id=?
            ORDER BY subject ASC, mastery_pct DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [
        {
            "subject": row[0],
            "chapter": row[1],
            "mastery_pct": round(float(row[2] or 0), 1),
            "quizzes_taken": int(row[3] or 0),
            "last_updated": row[4],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Streak calculation
# ---------------------------------------------------------------------------

def _calc_streak(activity_dates: List[str]) -> int:
    """Given a sorted list of 'YYYY-MM-DD' activity dates, return current streak."""
    if not activity_dates:
        return 0
    unique_days = sorted({d[:10] for d in activity_dates}, reverse=True)
    today = datetime.now(timezone.utc).date()
    streak = 0
    expected = today
    for day_str in unique_days:
        try:
            day = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day == expected or (streak == 0 and day == today - timedelta(days=1)):
            if streak == 0 and day != expected:
                # allow yesterday as start of streak if nothing today
                expected = day
            streak += 1
            expected = expected - timedelta(days=1)
        else:
            break
    return streak


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_dashboard(user_id: str) -> Dict:
    """
    Return aggregate progress stats for the user:
      - total_study_seconds, streak_days
      - totals: quizzes_taken, lessons_started, flashcard_sessions, assessments
      - top_subjects (by study time)
      - recent_activity (last 15 events)
      - subject_mastery summary
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # — Total study time & per-activity totals from time log —
        cursor.execute(
            """
            SELECT activity_type, SUM(duration_seconds), COUNT(*)
            FROM learning_time_log
            WHERE user_id=?
            GROUP BY activity_type
            """,
            (user_id,),
        )
        activity_rows = cursor.fetchall()

        total_study_seconds = 0
        activity_totals: Dict[str, int] = {}
        activity_counts: Dict[str, int] = {}
        for act_type, secs, cnt in activity_rows:
            total_study_seconds += int(secs or 0)
            activity_totals[act_type] = int(secs or 0)
            activity_counts[act_type] = int(cnt or 0)

        # — Streak from activity log —
        cursor.execute(
            "SELECT logged_at FROM learning_time_log WHERE user_id=? ORDER BY logged_at DESC LIMIT 365",
            (user_id,),
        )
        date_rows = [row[0] for row in cursor.fetchall()]
        streak_days = _calc_streak(date_rows)

        # — Counts from feature tables (ground truth) —
        cursor.execute("SELECT COUNT(*) FROM lesson_quizzes WHERE user_id=?", (user_id,))
        quiz_count = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM lesson_plans WHERE user_id=?", (user_id,))
        lesson_count = cursor.fetchone()[0] or 0

        # Count assessment papers + scored attempt snapshot
        try:
            cursor.execute("SELECT COUNT(*) FROM assessment_papers WHERE user_id=?", (user_id,))
            assessment_count = cursor.fetchone()[0] or 0
            assessment_summary = _get_assessment_summary(cursor, user_id)
        except Exception:
            assessment_count = 0
            assessment_summary = {}

        assignments = _list_assignments(cursor, user_id)

        # — Top subjects by logged study time —
        cursor.execute(
            """
            SELECT subject, SUM(duration_seconds) as total_secs
            FROM learning_time_log
            WHERE user_id=? AND subject != ''
            GROUP BY subject
            ORDER BY total_secs DESC
            LIMIT 8
            """,
            (user_id,),
        )
        top_subjects = [
            {"subject": row[0], "study_seconds": int(row[1] or 0)}
            for row in cursor.fetchall()
        ]

        # — Recent activity (last 15 events) —
        cursor.execute(
            """
            SELECT activity_type, subject, chapter, duration_seconds, logged_at
            FROM learning_time_log
            WHERE user_id=?
            ORDER BY id DESC LIMIT 15
            """,
            (user_id,),
        )
        recent_activity = [
            {
                "activity_type": row[0],
                "subject": row[1],
                "chapter": row[2],
                "duration_seconds": int(row[3] or 0),
                "logged_at": row[4],
            }
            for row in cursor.fetchall()
        ]

    finally:
        conn.close()

    # — Mastery summary (per subject average) —
    mastery_rows = get_mastery_stats(user_id)
    subject_mastery: Dict[str, Dict] = {}
    for m in mastery_rows:
        subj = m["subject"] or "General"
        if subj not in subject_mastery:
            subject_mastery[subj] = {"total_pct": 0.0, "count": 0, "chapters": []}
        subject_mastery[subj]["total_pct"] += m["mastery_pct"]
        subject_mastery[subj]["count"] += 1
        subject_mastery[subj]["chapters"].append(
            {"chapter": m["chapter"], "mastery_pct": m["mastery_pct"], "quizzes_taken": m["quizzes_taken"]}
        )

    mastery_summary = [
        {
            "subject": subj,
            "avg_mastery_pct": round(v["total_pct"] / v["count"], 1) if v["count"] else 0.0,
            "chapters_tracked": v["count"],
            "chapters": sorted(v["chapters"], key=lambda c: c["mastery_pct"], reverse=True),
        }
        for subj, v in subject_mastery.items()
    ]
    mastery_summary.sort(key=lambda x: x["avg_mastery_pct"], reverse=True)

    return {
        "total_study_seconds": total_study_seconds,
        "streak_days": streak_days,
        "totals": {
            "quizzes": quiz_count,
            "lessons": lesson_count,
            "assessments": assessment_count,
        },
        "top_subjects": top_subjects,
        "recent_activity": recent_activity,
        "mastery_summary": mastery_summary,
        "assessment_summary": assessment_summary,
        "assignments": assignments,
    }


def get_progress_insights(user_id: str) -> Dict:
    """Return lightweight coaching insights derived from the current dashboard."""
    dashboard = get_dashboard(user_id)
    total_study_seconds = int(dashboard.get("total_study_seconds") or 0)
    streak_days = int(dashboard.get("streak_days") or 0)
    totals = dashboard.get("totals") or {}
    mastery_summary = dashboard.get("mastery_summary") or []
    top_subjects = dashboard.get("top_subjects") or []
    assignments = dashboard.get("assignments") or []
    assessment_summary = dashboard.get("assessment_summary") or {}
    assessment_attempt_count = int(assessment_summary.get("attempt_count") or 0)
    assessment_average = int(assessment_summary.get("average_score_pct") or 0)
    assessment_latest = int(assessment_summary.get("latest_score_pct") or 0)
    assessment_subject = str(assessment_summary.get("latest_subject") or "").strip()
    assessment_due = assessment_attempt_count > 0 and (assessment_latest < 70 or assessment_average < 65)
    lesson_count = int(totals.get("lessons") or 0)
    quiz_count = int(totals.get("quizzes") or 0)
    assessment_start_ready = assessment_attempt_count == 0 and (lesson_count > 0 or quiz_count > 0)

    weakest_subject = None
    if mastery_summary:
        weakest_subject = min(mastery_summary, key=lambda item: float(item.get("avg_mastery_pct") or 0))

    if total_study_seconds <= 0:
        headline = "You’re ready to start your first study streak."
    elif streak_days >= 7:
        headline = f"Excellent consistency — you’re on a {streak_days}-day streak."
    elif streak_days >= 3:
        headline = f"Nice momentum — keep the {streak_days}-day streak going."
    elif assessment_due:
        headline = f"Your next best win is retrying {assessment_subject or 'your recent assessment'} with one focused checkpoint."
    elif assessment_start_ready:
        headline = f"You’re ready for a first {assessment_subject or (weakest_subject or {}).get('subject') or (top_subjects[0] or {}).get('subject') or 'subject'} assessment checkpoint."
    elif weakest_subject and float(weakest_subject.get("avg_mastery_pct") or 0) < 60:
        headline = f"Your next best win is strengthening {weakest_subject.get('subject') or 'your weakest topic'}."
    else:
        headline = "Your learning momentum is building well — keep stacking small wins."

    def build_recommendation(
        item_id: str,
        title: str,
        description: str,
        priority: str,
        *,
        action_tab: str = "chat",
        cta_label: str = "Open Chat",
        chapter_hint: str = "",
        context_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "id": item_id,
            "title": title,
            "description": description,
            "priority": priority,
            "action_tab": action_tab,
            "cta_label": cta_label,
            "chapter_hint": chapter_hint,
            "context_hint": context_hint or description,
        }

    recommendations: List[Dict] = []

    if total_study_seconds <= 0:
        recommendations.append(
            build_recommendation(
                "start-first-session",
                "Log your first study session",
                "Open a lesson or quiz and spend 10 focused minutes to kick off your progress data.",
                "high",
                action_tab="lesson",
                cta_label="Open Lesson",
            )
        )

    if streak_days == 0:
        recommendations.append(
            build_recommendation(
                "revive-streak",
                "Restart your streak today",
                "A short study burst today will put your streak back in motion.",
                "high",
                action_tab="lesson",
                cta_label="Start Lesson",
                chapter_hint=(weakest_subject or {}).get("subject") or "",
            )
        )

    if assessment_due:
        subject_name = assessment_subject or (weakest_subject or {}).get("subject") or ((top_subjects[0] or {}).get("subject") if top_subjects else "General")
        recommendations.append(
            build_recommendation(
                f"assessment-recovery-{subject_name.lower().replace(' ', '-')}",
                f"Retry {subject_name} assessment",
                f"Recent assessment performance is at {assessment_latest}% (avg {assessment_average}%). One exam-style retry can lift confidence and accuracy.",
                "high" if assessment_latest < 60 or assessment_average < 60 else "medium",
                action_tab="assessment",
                cta_label="Retry Assessment",
                chapter_hint=subject_name,
                context_hint=f"Use one exam-style checkpoint to improve recent {subject_name} scores.",
            )
        )
    elif assessment_start_ready:
        subject_name = assessment_subject or (weakest_subject or {}).get("subject") or ((top_subjects[0] or {}).get("subject") if top_subjects else "General")
        recommendations.append(
            build_recommendation(
                f"assessment-start-{subject_name.lower().replace(' ', '-')}",
                f"Start a {subject_name} assessment",
                f"You’ve built enough momentum to check how well {subject_name} is sticking with one exam-style assessment.",
                "medium",
                action_tab="assessment",
                cta_label="Start Assessment",
                chapter_hint=subject_name,
                context_hint=f"Use one exam-style checkpoint to measure your current {subject_name} understanding.",
            )
        )

    if weakest_subject and float(weakest_subject.get("avg_mastery_pct") or 0) < 70:
        subject_name = weakest_subject.get("subject") or "your current subject"
        description = f"Mastery is at {round(float(weakest_subject.get('avg_mastery_pct') or 0), 1)}%. A quick revision quiz can raise it fast."
        recommendations.append(
            build_recommendation(
                f"review-{subject_name.lower().replace(' ', '-')}",
                f"Review {subject_name}",
                description,
                "medium",
                action_tab="quiz",
                cta_label="Open Review Quiz",
                chapter_hint=subject_name,
                context_hint=f"Use a short {subject_name} quiz to strengthen the weakest area.",
            )
        )

    if int(totals.get("quizzes") or 0) < max(1, int(totals.get("lessons") or 0)):
        focus_hint = (weakest_subject or {}).get("subject") or ((top_subjects[0] or {}).get("subject") if top_subjects else "")
        recommendations.append(
            build_recommendation(
                "add-quiz-checkpoint",
                "Add a quick quiz checkpoint",
                "Follow up your lessons with a quiz to lock in retention and improve mastery tracking.",
                "medium",
                action_tab="quiz",
                cta_label="Start Quiz",
                chapter_hint=focus_hint or "General",
            )
        )

    if not top_subjects:
        recommendations.append(
            build_recommendation(
                "explore-subjects",
                "Build your subject history",
                "Study across one or two subjects this week so the app can surface smarter recommendations.",
                "low",
                action_tab="lesson",
                cta_label="Open Lesson",
            )
        )

    if not recommendations:
        focus_subject = (top_subjects[0] or {}).get("subject") if top_subjects else None
        recommendations.append(
            build_recommendation(
                "keep-momentum",
                "Keep the momentum going",
                f"Return to {focus_subject} for another focused session to extend your consistency." if focus_subject else "Repeat one of your recent study activities to keep the trend positive.",
                "low",
                action_tab="lesson" if focus_subject else "chat",
                cta_label="Open Lesson" if focus_subject else "Open Chat",
                chapter_hint=focus_subject or "",
            )
        )

    best_mastery = max((float(item.get("avg_mastery_pct") or 0) for item in mastery_summary), default=0.0)
    quiz_count = int(totals.get("quizzes") or 0)

    badges = [
        {
            "id": "study-starter",
            "label": "Study Starter",
            "description": "Log at least 10 minutes of study time.",
            "earned": total_study_seconds >= 600,
            "progress_pct": min(100, int((total_study_seconds / 600) * 100)) if total_study_seconds > 0 else 0,
        },
        {
            "id": "streak-builder",
            "label": "Streak Builder",
            "description": "Reach a 3-day learning streak.",
            "earned": streak_days >= 3,
            "progress_pct": min(100, int((streak_days / 3) * 100)) if streak_days > 0 else 0,
        },
        {
            "id": "quiz-explorer",
            "label": "Quiz Explorer",
            "description": "Complete 5 quizzes to build confidence.",
            "earned": quiz_count >= 5,
            "progress_pct": min(100, int((quiz_count / 5) * 100)) if quiz_count > 0 else 0,
        },
        {
            "id": "mastery-riser",
            "label": "Mastery Riser",
            "description": "Reach 75% mastery in any tracked subject.",
            "earned": best_mastery >= 75,
            "progress_pct": min(100, int((best_mastery / 75) * 100)) if best_mastery > 0 else 0,
        },
    ]

    notifications: List[Dict[str, Any]] = []

    open_assignments = [
        item for item in assignments
        if str(item.get("status") or "assigned").strip().lower() == "assigned"
    ]
    overdue_assignments: List[Dict[str, Any]] = []
    due_soon_assignments: List[Dict[str, Any]] = []
    today = datetime.now(timezone.utc).date()

    for item in open_assignments:
        due_at = _parse_due_label_date(item.get("due_label"))
        if not due_at:
            continue
        due_date = due_at.date()
        if due_date < today:
            overdue_assignments.append(item)
        elif due_date <= today + timedelta(days=3):
            due_soon_assignments.append(item)

    if overdue_assignments:
        first_assignment = overdue_assignments[0]
        notifications.append(
            {
                "id": f"overdue-assignment-{first_assignment.get('id')}",
                "title": "Overdue assignment",
                "message": f"{first_assignment.get('title') or 'An assigned task'} was due {first_assignment.get('due_label')}. Complete or reschedule it today.",
                "severity": "high",
                "action_tab": first_assignment.get("action_tab") or "lesson",
                "cta_label": first_assignment.get("cta_label") or "Open Assignment",
                "chapter_hint": first_assignment.get("chapter_hint") or "",
                "context_hint": first_assignment.get("context_hint") or first_assignment.get("description") or "",
            }
        )
    elif due_soon_assignments:
        first_assignment = due_soon_assignments[0]
        notifications.append(
            {
                "id": f"due-soon-assignment-{first_assignment.get('id')}",
                "title": "Assignment due soon",
                "message": f"{first_assignment.get('title') or 'An assigned task'} is due {first_assignment.get('due_label')}. A quick session now will keep you on track.",
                "severity": "medium",
                "action_tab": first_assignment.get("action_tab") or "lesson",
                "cta_label": first_assignment.get("cta_label") or "Open Assignment",
                "chapter_hint": first_assignment.get("chapter_hint") or "",
                "context_hint": first_assignment.get("context_hint") or first_assignment.get("description") or "",
            }
        )
    elif open_assignments:
        first_assignment = open_assignments[0]
        notifications.append(
            {
                "id": f"pending-assignment-{first_assignment.get('id')}",
                "title": "Pending assignment",
                "message": first_assignment.get("description") or f"You have an assigned {first_assignment.get('action_tab') or 'study'} task waiting.",
                "severity": "high",
                "action_tab": first_assignment.get("action_tab") or "lesson",
                "cta_label": first_assignment.get("cta_label") or "Open Assignment",
                "chapter_hint": first_assignment.get("chapter_hint") or "",
                "context_hint": first_assignment.get("context_hint") or first_assignment.get("description") or "",
            }
        )

    if streak_days <= 1 and total_study_seconds > 0:
        notifications.append(
            {
                "id": "keep-streak-alive",
                "title": "Keep your streak alive",
                "message": "A short session today will keep your momentum moving in the right direction.",
                "severity": "medium",
                "action_tab": "lesson",
                "cta_label": "Open Lesson",
                "chapter_hint": (weakest_subject or {}).get("subject") or ((top_subjects[0] or {}).get("subject") if top_subjects else ""),
                "context_hint": "A short session today will keep your momentum moving in the right direction.",
            }
        )

    if assessment_due:
        notifications.append(
            {
                "id": "assessment-reminder",
                "title": "Assessment reminder",
                "message": f"Your recent assessment trend ({assessment_latest}% latest) is ready for one focused retry.",
                "severity": "high" if assessment_latest < 60 else "medium",
                "action_tab": "assessment",
                "cta_label": "Retry Assessment",
                "chapter_hint": assessment_subject or (weakest_subject or {}).get("subject") or "",
                "context_hint": f"Your recent assessment trend ({assessment_latest}% latest) is ready for one focused retry.",
            }
        )

    return {
        "headline": headline,
        "recommendations": recommendations[:3],
        "badges": badges,
        "notifications": notifications[:4],
    }


def get_study_plan(user_id: str) -> Dict:
    """Build a short adaptive weekly study plan from progress and insight data."""
    dashboard = get_dashboard(user_id)
    insights = get_progress_insights(user_id)

    mastery_summary = dashboard.get("mastery_summary") or []
    top_subjects = dashboard.get("top_subjects") or []
    recent_activity = dashboard.get("recent_activity") or []
    totals = dashboard.get("totals") or {}
    streak_days = int(dashboard.get("streak_days") or 0)
    total_study_seconds = int(dashboard.get("total_study_seconds") or 0)
    lesson_count = int(totals.get("lessons") or 0)
    quiz_count = int(totals.get("quizzes") or 0)
    recent_chat_count = sum(1 for item in recent_activity if item.get("activity_type") == ACTIVITY_CHAT)
    recent_lesson_count = sum(1 for item in recent_activity if item.get("activity_type") == ACTIVITY_LESSON)
    recent_quiz_count = sum(1 for item in recent_activity if item.get("activity_type") == ACTIVITY_QUIZ)
    assessment_summary = dashboard.get("assessment_summary") or {}
    assessment_attempt_count = int(assessment_summary.get("attempt_count") or 0)
    assessment_average = int(assessment_summary.get("average_score_pct") or 0)
    assessment_latest = int(assessment_summary.get("latest_score_pct") or 0)
    week_key = _get_week_key()
    manual_overrides = _load_study_plan_overrides(user_id, week_key)

    focus_subject = "General"
    if mastery_summary:
        weakest_subject = min(mastery_summary, key=lambda item: float(item.get("avg_mastery_pct") or 0))
        focus_subject = weakest_subject.get("subject") or "General"
    elif top_subjects:
        focus_subject = top_subjects[0].get("subject") or "General"

    if focus_subject == "General":
        headline = "Build a balanced study rhythm this week with one lesson, one quiz, and one review block."
    elif streak_days >= 3:
        headline = f"This week, build on your momentum by doubling down on {focus_subject}."
    else:
        headline = f"This week, focus on strengthening {focus_subject} with short, consistent practice."

    lead_recommendation = (insights.get("recommendations") or [{}])[0]
    recommendation_text = lead_recommendation.get("description") or f"Spend focused time revising {focus_subject}."

    review_completed = lesson_count > 0 or recent_lesson_count > 0 or total_study_seconds >= 900
    quiz_completed = quiz_count > 0 or recent_quiz_count > 0
    assessment_due = assessment_attempt_count > 0 and (assessment_latest < 70 or assessment_average < 65)
    assessment_completed = assessment_attempt_count > 0 and assessment_latest >= 70
    recap_completed = recent_chat_count > 0 or streak_days >= 2 or total_study_seconds >= 1800

    middle_step = {
        "id": "quiz-checkpoint",
        "title": f"Take a quick {focus_subject} quiz",
        "description": "Use a short quiz session to check recall and lift your mastery score.",
        "duration_minutes": 10,
        "activity_type": "quiz",
        "action_tab": "quiz",
        "cta_label": "Retry Quiz" if quiz_completed else "Start Quiz",
        "chapter_hint": focus_subject,
        "context_hint": f"Check recall with a short {focus_subject} quiz.",
        "completed": quiz_completed,
    }

    if assessment_due:
        middle_step = {
            "id": "assessment-checkpoint",
            "title": f"Retry a {focus_subject} assessment",
            "description": f"Use one exam-style checkpoint to improve from your latest {assessment_latest}% score.",
            "duration_minutes": 15,
            "activity_type": "assessment",
            "action_tab": "assessment",
            "cta_label": "Retry Assessment" if assessment_attempt_count > 0 else "Start Assessment",
            "chapter_hint": focus_subject,
            "context_hint": f"Generate an exam-style {focus_subject} assessment focused on improving from my recent scores.",
            "completed": assessment_completed,
            "auto_run": True,
            "mode_hint": "exam",
            "difficulty_hint": "mixed",
            "question_count_hint": 5,
        }

    schedule = [
        {
            "id": "review-block",
            "title": f"Review {focus_subject} notes",
            "description": recommendation_text,
            "duration_minutes": 15,
            "activity_type": "lesson",
            "action_tab": "lesson",
            "cta_label": "Review Lesson" if review_completed else "Open Lesson",
            "chapter_hint": focus_subject,
            "context_hint": recommendation_text,
            "completed": review_completed,
        },
        middle_step,
        {
            "id": "reflect-and-repeat",
            "title": "Finish with a recap",
            "description": "Write or say the three key ideas you learned, then log one more short session tomorrow.",
            "duration_minutes": 5,
            "activity_type": "chat",
            "action_tab": "chat",
            "cta_label": "Open Chat",
            "chapter_hint": focus_subject,
            "context_hint": f"Help me recap the key ideas from {focus_subject} and what to study next.",
            "completed": recap_completed,
        },
    ]

    target_minutes = 30
    target_lessons = 1
    target_quizzes = 1
    study_minutes = max(0, round(total_study_seconds / 60))

    targets = [
        {
            "id": "study-minutes",
            "label": "Study time",
            "current": study_minutes,
            "target": target_minutes,
            "unit": "min",
            "completed": study_minutes >= target_minutes,
            "progress_pct": min(100, int((study_minutes / target_minutes) * 100)) if target_minutes else 0,
            "activity_type": "lesson",
            "action_tab": "lesson",
            "cta_label": "Open Focus Lesson",
            "chapter_hint": focus_subject,
            "context_hint": f"Spend 15 more minutes reviewing {focus_subject}.",
        },
        {
            "id": "weekly-lessons",
            "label": "Lessons",
            "current": lesson_count,
            "target": target_lessons,
            "unit": "done",
            "completed": lesson_count >= target_lessons or recent_lesson_count >= target_lessons,
            "progress_pct": min(100, int((max(lesson_count, recent_lesson_count) / target_lessons) * 100)) if target_lessons else 0,
            "activity_type": "lesson",
            "action_tab": "lesson",
            "cta_label": "Review Lesson Goal",
            "chapter_hint": focus_subject,
            "context_hint": f"Open a focused {focus_subject} lesson to stay on track.",
        },
        {
            "id": "weekly-quiz",
            "label": "Quizzes",
            "current": quiz_count,
            "target": target_quizzes,
            "unit": "done",
            "completed": quiz_count >= target_quizzes or recent_quiz_count >= target_quizzes,
            "progress_pct": min(100, int((max(quiz_count, recent_quiz_count) / target_quizzes) * 100)) if target_quizzes else 0,
            "activity_type": "quiz",
            "action_tab": "quiz",
            "cta_label": "Practice Quiz Goal",
            "chapter_hint": focus_subject,
            "context_hint": f"Use one quick quiz in {focus_subject} to stay on track with your weekly goal.",
        },
    ]

    for step in schedule:
        override_key = f"schedule::{step.get('id')}"
        if override_key in manual_overrides:
            step["completed"] = manual_overrides[override_key]
        step["can_toggle_completion"] = True

    for target in targets:
        override_key = f"goal::{target.get('id')}"
        if override_key in manual_overrides:
            target["completed"] = manual_overrides[override_key]
        target["can_toggle_completion"] = True

    next_step_assigned = False
    for step in schedule:
        if step.get("completed"):
            step["status"] = "done"
            step["status_label"] = "Done"
        elif not next_step_assigned:
            step["status"] = "next"
            step["status_label"] = "Next up"
            next_step_assigned = True
        else:
            step["status"] = "upcoming"
            step["status_label"] = "Coming up"

    goal_summary = {
        "completed": sum(1 for target in targets if target.get("completed")),
        "total": len(targets),
    }

    if schedule and all(step.get("completed") for step in schedule):
        headline = (
            f"You’re on track in {focus_subject} — keep the rhythm going with one more quick check-in."
            if focus_subject != "General"
            else "You’re on track this week — keep the rhythm going with one more quick check-in."
        )

    snapshot_payload = {
        "headline": headline,
        "focus_subject": focus_subject,
        "schedule": schedule,
        "goal_summary": goal_summary,
        "targets": targets,
    }
    _save_study_plan_snapshot(user_id, week_key, snapshot_payload)
    history = _load_study_plan_history(user_id, week_key, snapshot_payload)

    return {
        **snapshot_payload,
        "history": history,
    }
