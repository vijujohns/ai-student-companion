"""
REST APIs
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, UploadFile, File, Form
from ..modules.rag import generate_answer
from ..modules.history import get_history
from ..modules.db import get_connection
from ..modules.dependencies import require_role, get_current_user, validate_session_ownership, require_quota
from ..modules.messages import envelope, get_message
from ..modules.policy import consume_quota, release_usage
from ..modules.adapters import get_default_service_registry
import uuid
from typing import Any, Callable, Optional
from fastapi.responses import FileResponse
from urllib.parse import unquote
import json
import os
from ..modules.flashcards import router as flashcards_router
from ..modules.model_manager import (
    CLOUD_MODELS,
    LOCAL_MODELS,
    get_active_model_profile_key,
    get_model_profiles,
    is_model_available,
    list_models,
    set_active_model_profile_key,
)
from ..modules.task_router import route_task
from ..modules.generator_executor import execute_generator_task, is_generator_task
from ..modules.utility_executor import execute_utility_task, is_utility_task
from .common import _consume_quota_or_raise, _log_progress_activity_safe, services
from .health import router as health_router
from .ask import router as ask_router
from .admin import router as admin_router
from .auth_session import router as auth_session_router
from .knowledge import router as knowledge_router
from .lesson_plan import router as lesson_plan_router
from .quiz import router as quiz_router
from .assessment import router as assessment_router
from .progress import router as progress_router
from .collaboration import router as collaboration_router
from .subscription import router as subscription_router

# ✅ Import Pydantic schemas for validation
from ..schemas.request import (
    AskRequest, ContextSelectionRequest,
    LessonPlanCreateRequest, LessonProgressRequest, QuizGenerateRequest,
    QuizSubmitRequest, FlashcardCreateRequest, ArtifactGenerateRequest, RenameSessionRequest,
    SubjectQuizRequest, QuestionPaperRequest, AssessmentAttemptRequest, LogActivityRequest,
    TranslateRequest, PreferencesUpdateRequest, AdminModelProfileUpdateRequest,
    StudyPlanItemUpdateRequest,
)
from ..schemas.response import (
    LoginResponse, AskResponse, SessionListResponse, SessionContentResponse,
    ClassResponse, SubjectResponse, ContentsResponse, QuizResponse,
    LessonPlanResponse, ErrorResponse
)

router = APIRouter()

DEFAULT_REMINDER_SETTINGS = {
    "enabled": True,
    "frequency": "daily",
    "muted_ids": [],
}

router.include_router(flashcards_router)
router.include_router(auth_session_router)
router.include_router(health_router)
router.include_router(ask_router)
router.include_router(knowledge_router)
router.include_router(lesson_plan_router)
router.include_router(quiz_router)
router.include_router(assessment_router)
router.include_router(admin_router)
router.include_router(progress_router)
router.include_router(collaboration_router)
router.include_router(subscription_router)


def _health_result(status: str = "ok", **details: Any) -> dict:
    result = {"status": status}
    result.update(details)
    return result


def _safe_health_check(check: Callable[[], dict]) -> dict:
    try:
        return check()
    except Exception as exc:
        return _health_result("degraded", error=str(exc))


def _health_check_database() -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
    finally:
        conn.close()
    return _health_result("ok", reachable=True)


def _health_check_cache() -> dict:
    from ..modules import cache

    client = getattr(cache, "r", None)
    if client is None:
        client_type = "uninitialized"
    elif client.__class__.__name__ == "InMemoryCache":
        client_type = "in-memory"
    else:
        client_type = "redis"

    breaker = getattr(cache, "CIRCUIT_BREAKER", {}) or {}
    status = "degraded" if breaker.get("is_open") or client_type in {"in-memory", "uninitialized"} else "ok"
    return _health_result(
        status,
        client_type=client_type,
        redis_host=str(getattr(cache, "REDIS_HOST", "")),
        redis_port=int(getattr(cache, "REDIS_PORT", 0) or 0),
        circuit_open=bool(breaker.get("is_open")),
        failure_count=int(breaker.get("failure_count") or 0),
    )


def _health_check_faiss() -> dict:
    from ..modules import faiss_store

    logical_indexes = getattr(faiss_store, "logical_indexes", {}) or {}
    documents = getattr(faiss_store, "documents", []) or []
    return _health_result(
        "ok",
        documents_count=len(documents),
        logical_indexes_count=len(logical_indexes),
        index_file_exists=os.path.exists(getattr(faiss_store, "INDEX_FILE", "")),
        documents_file_exists=os.path.exists(getattr(faiss_store, "DOC_FILE", "")),
        metadata_file_exists=os.path.exists(getattr(faiss_store, "META_FILE", "")),
    )


def _health_check_ocr() -> dict:
    from ..modules.ocr import get_ocr_status

    ocr = get_ocr_status()
    return _health_result(
        "ok" if ocr.get("available") else "degraded",
        available=bool(ocr.get("available")),
        engine=str(ocr.get("engine") or "none"),
        message=str(ocr.get("message") or ""),
    )


def _health_check_models() -> dict:
    models = list_models()
    available = [name for name in models if is_model_available(name)]
    profiles = get_model_profiles()
    return _health_result(
        "ok" if available else "degraded",
        active_profile=get_active_model_profile_key(),
        configured_models_count=len(models),
        available_models_count=len(available),
        configured_profiles_count=len(profiles),
        local_models_count=len(LOCAL_MODELS),
        cloud_models_count=len(CLOUD_MODELS),
        available_models=available,
    )


def _runtime_diagnostic_checks() -> dict:
    return {
        "database": _safe_health_check(_health_check_database),
        "cache": _safe_health_check(_health_check_cache),
        "faiss": _safe_health_check(_health_check_faiss),
        "ocr": _safe_health_check(_health_check_ocr),
        "models": _safe_health_check(_health_check_models),
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
    """Allow empty/new sessions, but block access to sessions owned by others."""
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


def _log_progress_activity_safe(
    user: dict,
    activity_type: str,
    *,
    subject: str = "",
    chapter: str = "",
    duration_seconds: int = 0,
) -> None:
    """Best-effort progress logging; never interrupt the primary learning flow."""
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


# The health, ask, and admin endpoints have been migrated into dedicated router modules.
# Remaining route definitions continue below.


def _get_user_row_by_email(email: str):
    return services.relationships.get_user_by_email(email)


def _resolve_student_user_id(student_identifier: str) -> Optional[str]:
    return services.relationships.resolve_student_user_id(student_identifier)


def _has_relationship_access(student_user_id: str, requester: dict) -> bool:
    return services.relationships.has_relationship_access(student_user_id, requester)


# ✅ MOVED TO auth_session.py router
# - POST /login
# - GET /auth/session
# - POST /logout
# - POST /register


# ✅ MOVED TO auth_session.py router
# - GET /profile
# - PUT /profile
# - POST /reset-password


# ✅ MOVED TO auth_session.py router
# - GET /sessions
# - DELETE /sessions/{session_id}
# - PUT /sessions/{session_id}
# - GET /sessions/{session_id}/content
# - PUT /sessions/{session_id}/content


@router.get("/context")
def get_learning_context(user=Depends(get_current_user)):
    """Return the current user's saved learning context / explorer mode."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT context_mode, class_name, subject_name, folder_name, content_id
            FROM user_preferences
            WHERE user_id=?
            LIMIT 1
            """,
            (user["username"],),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    return envelope(
        {
            "mode": (row[0] if row and len(row) > 0 and row[0] else "contextual"),
            "class_name": row[1] if row and len(row) > 1 else None,
            "subject_name": row[2] if row and len(row) > 2 else None,
            "folder_name": row[3] if row and len(row) > 3 else None,
            "content_id": row[4] if row and len(row) > 4 else None,
        },
        message_id="MSG-1000",
    )


@router.post("/context")
def set_learning_context(request: ContextSelectionRequest, user=Depends(get_current_user)):
    """Persist the user's global learning context / explorer mode selection."""
    from datetime import datetime, timezone

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO user_preferences (
                user_id,
                preferred_language,
                reminder_settings,
                context_mode,
                class_name,
                subject_name,
                folder_name,
                content_id,
                updated_at
            )
            VALUES (?, 'en', '{}', ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                context_mode=excluded.context_mode,
                class_name=excluded.class_name,
                subject_name=excluded.subject_name,
                folder_name=excluded.folder_name,
                content_id=excluded.content_id,
                updated_at=excluded.updated_at
            """,
            (
                user["username"],
                request.mode,
                request.class_name,
                request.subject_name,
                request.folder_name,
                request.content_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return envelope(
        {
            "mode": request.mode,
            "class_name": request.class_name,
            "subject_name": request.subject_name,
            "folder_name": request.folder_name,
            "content_id": request.content_id,
            "updated": True,
        },
        message_id="MSG-1000",
    )






# -------------------------
# Quiz Endpoints
# -------------------------

@router.get("/flashcards/sessions", response_model=SessionListResponse)
def api_list_flashcard_sessions(
    limit: Optional[int] = Query(None, ge=1, le=100),
    offset: Optional[int] = Query(None, ge=0),
    user=Depends(get_current_user),
):
    """Return saved flashcard sessions for the current user."""
    page = services.learning.list_flashcard_sessions(user["username"], limit=limit, offset=offset)
    return envelope({"sessions": page["items"], "pagination": page["pagination"]}, message_id="MSG-1000")


@router.get("/flashcards/latest")
def api_get_latest_flashcards(session_id: str, user=Depends(get_current_user)):
    artifact = services.learning.get_latest_flashcards(user["username"], session_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Flashcards not found")
    return envelope({"artifact": artifact}, message_id="MSG-1000")


@router.put("/flashcards/sessions/{session_id}")
def rename_flashcard_session_endpoint(session_id: str, request: RenameSessionRequest, user=Depends(get_current_user)):
    result = services.learning.rename_flashcard_session(user["username"], session_id, request.title)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Flashcard session not found")
    return envelope(result, message_id="MSG-1000")


@router.delete("/flashcards/sessions/{session_id}")
def delete_flashcard_session_endpoint(session_id: str, user=Depends(get_current_user)):
    result = services.learning.delete_flashcard_session(user["username"], session_id)
    return envelope(result, message_id="MSG-1000")




def _infer_subject_chapter(user_id: str, session_id: str) -> tuple[str, str]:
    """Best-effort lookup of subject/chapter from lesson plan for a session."""
    try:
        from ..modules.db import get_connection as _gc
        conn = _gc()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT chapter FROM lesson_plans WHERE user_id=? AND session_id=? ORDER BY id DESC LIMIT 1",
            (user_id, session_id),
        )
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            chapter = row[0]
            # Treat the chapter as subject if no more specific mapping
            return chapter, chapter
    except Exception:
        pass
    return "", ""


# ---------------------------------------------------------------------------
# Progress Intelligence: analytics, mastery, activity logging
# ---------------------------------------------------------------------------

@router.get("/progress/dashboard")
def api_progress_dashboard(user=Depends(get_current_user)):
    """Return aggregate study stats, streak, top subjects, and mastery summary."""
    return envelope(services.progress.get_dashboard(user["username"]), message_id="MSG-1000")


@router.get("/progress/mastery")
def api_progress_mastery(user=Depends(get_current_user)):
    """Return per-subject/chapter mastery scores for the current user."""
    return envelope({"mastery": services.progress.get_mastery_stats(user["username"])}, message_id="MSG-1000")


@router.get("/progress/insights")
def api_progress_insights(user=Depends(get_current_user)):
    """Return recommendation and badge-style coaching insights for the current user."""
    return envelope(services.progress.get_insights(user["username"]), message_id="MSG-1000")


@router.get("/progress/study-plan")
def api_progress_study_plan(user=Depends(get_current_user)):
    """Return an adaptive short-form study plan for the current user."""
    return envelope(services.progress.get_study_plan(user["username"]), message_id="MSG-1000")


@router.post("/progress/study-plan/items/{item_id}")
def api_progress_study_plan_item(item_id: str, request: StudyPlanItemUpdateRequest, user=Depends(get_current_user)):
    """Persist a manual completion update for a schedule step or weekly goal target."""
    saved = services.progress.update_study_plan_item(
        user_id=user["username"],
        item_id=item_id,
        item_type=request.item_type,
        completed=request.completed,
    )
    return envelope(saved, message_id="MSG-1000")


@router.post("/progress/activity")
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


# =============================================================================
# Language / Translation / Preferences  (#4 — Multilingual + Accessibility)
# =============================================================================

@router.get("/languages")
def api_list_languages():
    """Return all supported language codes and names for the multilingual UI."""
    from ..modules.translation import list_languages
    return envelope({"languages": list_languages()}, message_id="MSG-1000")


@router.post("/translate")
def api_translate(request: TranslateRequest, user=Depends(get_current_user)):
    """
    Translate *text* to *target_language*.

    The response includes the translated text, the target language code,
    and the user's currently stored preferred language.
    """
    from ..modules.translation import translate_text
    translated = translate_text(
        request.text,
        target=request.target_language,
        source=request.source_language,
    )
    return envelope(
        {
            "translated_text": translated,
            "target_language": request.target_language,
            "source_language": request.source_language,
        },
        message_id="MSG-1000",
    )


@router.get("/preferences")
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


@router.put("/preferences")
def api_update_preferences(request: PreferencesUpdateRequest, user=Depends(get_current_user)):
    """Persist the user's language preference and reminder settings."""
    from datetime import datetime, timezone
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


@router.get("/admin/model-profiles")
def api_get_model_profiles(user=Depends(require_role("admin"))):
    """Return the active global model behavior profile and all configured profile options."""
    return envelope(
        {
            "active_profile": get_active_model_profile_key(force_refresh=True),
            "profiles": get_model_profiles(),
            "scope": "global",
        },
        message_id="MSG-1000",
    )


@router.put("/admin/model-profiles")
def api_update_model_profiles(request: AdminModelProfileUpdateRequest, user=Depends(require_role("admin"))):
    """Persist the globally active model behavior profile for all users."""
    result = set_active_model_profile_key(request.profile_key, updated_by=user.get("username", "admin"))
    return envelope(
        {
            "active_profile": result["active_profile"],
            "profiles": get_model_profiles(),
            "scope": "global",
            "updated": True,
        },
        message_id="MSG-1000",
    )


@router.get("/ocr/status")
def api_ocr_status(user=Depends(get_current_user)):
    """Return whether Tesseract OCR is available on the server."""
    from ..modules.ocr import get_ocr_status
    return envelope(get_ocr_status(), message_id="MSG-1000")


@router.post("/upload/file")
async def api_upload_file(
    upload: UploadFile = File(...),
    class_name: str = Form(...),
    subject_name: str = Form(...),
    folder_name: str = Form(...),
    display_name: str = Form(...),
    user=Depends(get_current_user),
):
    """
    Upload a PDF **or image** (JPEG, PNG, GIF, WEBP) and queue it for indexing.
    Images are processed via OCR; PDFs use standard text extraction.
    """
    result = upload_file(
        user=user,
        upload=upload,
        class_name=class_name,
        subject_name=subject_name,
        folder_name=folder_name,
        display_name=display_name,
    )
    return envelope(result, message_id="MSG-1000")
