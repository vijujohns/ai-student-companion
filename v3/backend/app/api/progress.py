from fastapi import APIRouter, Depends, HTTPException
from ..modules.adapters import get_default_service_registry
from ..modules.db import get_connection
from ..modules.dependencies import get_current_user
from ..modules.messages import envelope
from ..schemas.request import StudyPlanItemUpdateRequest, LogActivityRequest, PreferencesUpdateRequest
from ..schemas.response import (
    PreferencesResponse,
    ProgressDashboardResponse,
    ProgressMasteryResponse,
    ProgressInsightsResponse,
    ProgressStudyPlanResponse,
    ActivityLogResponse,
)
import json
from datetime import datetime, timezone

router = APIRouter()
services = get_default_service_registry()

DEFAULT_REMINDER_DELIVERY_SCOPE = "local-only"


@router.get("/progress/dashboard", response_model=ProgressDashboardResponse)
def api_progress_dashboard(user=Depends(get_current_user)):
    """Return aggregate study stats, streak, top subjects, and mastery summary."""
    return envelope(services.progress.get_dashboard(user["username"]), message_id="MSG-1000")


@router.get("/progress/mastery", response_model=ProgressMasteryResponse)
def api_progress_mastery(user=Depends(get_current_user)):
    """Return per-subject/chapter mastery scores for the current user."""
    return envelope({"mastery": services.progress.get_mastery_stats(user["username"])}, message_id="MSG-1000")


@router.get("/progress/insights", response_model=ProgressInsightsResponse)
def api_progress_insights(user=Depends(get_current_user)):
    """Return recommendation and badge-style coaching insights for the current user."""
    return envelope(services.progress.get_insights(user["username"]), message_id="MSG-1000")


@router.get("/progress/study-plan", response_model=ProgressStudyPlanResponse)
def api_progress_study_plan(user=Depends(get_current_user)):
    """Return an adaptive short-form study plan for the current user."""
    return envelope(services.progress.get_study_plan(user["username"]), message_id="MSG-1000")


@router.post("/progress/study-plan/items/{item_id}", response_model=ActivityLogResponse)
def api_progress_study_plan_item(item_id: str, request: StudyPlanItemUpdateRequest, user=Depends(get_current_user)):
    """Persist a manual completion update for a schedule step or weekly goal target."""
    saved = services.progress.update_study_plan_item(
        user_id=user["username"],
        item_id=item_id,
        item_type=request.item_type,
        completed=request.completed,
    )
    return envelope(saved, message_id="MSG-1000")


@router.post("/progress/activity", response_model=ActivityLogResponse)
def api_log_activity(request: LogActivityRequest, user=Depends(get_current_user)):
    """Log a study activity event (called by client on tab switch or session end)."""
    row_id = services.progress.log_activity(
        user_id=user["username"],
        activity_type=request.activity_type,
        subject=request.subject or "",
        chapter=request.chapter or "",
        duration_seconds=request.duration_seconds,
    )
    return envelope({"logged": True, "activity_id": row_id}, message_id="MSG-1000")


@router.get("/preferences", response_model=PreferencesResponse)
def api_get_preferences(user=Depends(get_current_user)):
    """Return the current user's stored preferences."""
    user_id = user["username"]
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT preferred_language, reminder_settings FROM user_preferences WHERE user_id=? LIMIT 1",
            (user_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    preferred_language = row[0] if row else "en"
    reminder_settings = _normalize_reminder_settings(row[1] if row and len(row) > 1 else None)
    return envelope(
        {"preferred_language": preferred_language, "reminder_settings": reminder_settings},
        message_id="MSG-1000",
    )


@router.put("/preferences", response_model=PreferencesResponse)
def api_update_preferences(request: PreferencesUpdateRequest, user=Depends(get_current_user)):
    """Persist the user's language preference and reminder settings."""
    user_id = user["username"]
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT reminder_settings FROM user_preferences WHERE user_id=? LIMIT 1",
            (user_id,),
        )
        existing = cur.fetchone()
        reminder_settings = _normalize_reminder_settings(
            request.reminder_settings.model_dump() if request.reminder_settings is not None else (existing[0] if existing else None)
        )

        cur.execute(
            """
            INSERT INTO user_preferences (user_id, preferred_language, reminder_settings, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                preferred_language=excluded.preferred_language,
                reminder_settings=excluded.reminder_settings,
                updated_at=excluded.updated_at
            """,
            (
                user_id,
                request.preferred_language,
                json.dumps(reminder_settings),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return envelope(
        {"preferred_language": request.preferred_language, "reminder_settings": reminder_settings, "updated": True},
        message_id="MSG-1000",
    )


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

    frequency = str(raw_settings.get("frequency") or "daily").strip().lower()
    if frequency not in {"all", "daily", "important-only", "weekly", "off"}:
        frequency = "daily"

    delivery_scope = str(raw_settings.get("delivery_scope") or DEFAULT_REMINDER_DELIVERY_SCOPE).strip().lower()
    if delivery_scope not in {"local-only", "server", "hybrid"}:
        delivery_scope = DEFAULT_REMINDER_DELIVERY_SCOPE

    return {
        "enabled": bool(raw_settings.get("enabled", True)),
        "frequency": frequency,
        "muted_ids": [str(item).strip() for item in muted_ids if str(item).strip()][:25],
        "delivery_scope": delivery_scope,
    }
