"""
REST APIs
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Response, UploadFile, File, Form
from ..modules.rag import generate_answer
from ..modules.history import get_history
from ..modules.db import get_connection
from ..modules.dependencies import require_role, get_current_user, validate_session_ownership, require_quota
from ..modules.messages import envelope, get_message
from ..modules.policy import consume_quota, release_usage
from ..modules.adapters import get_default_service_registry
from ..modules.assessment import (
    generate_subject_quiz,
    generate_question_paper,
    get_assessment_paper,
    list_assessment_papers,
    record_assessment_attempt,
)
from ..modules.file_management import (
    resolve_content_reference,
    upload_pdf,
    upload_file,
)
import uuid
from typing import Optional
from fastapi.responses import FileResponse
from urllib.parse import unquote
import json
import os
from ..modules.flashcards import router as flashcards_router
from ..modules.lesson_plan import (
    generate_lesson_plan,
    get_lesson_plan,
    get_lesson_plan_cards,
    complete_lesson_card,
    get_card_for_user,
    update_step_progress,
    get_next_step,
    list_lesson_sessions,
    rename_lesson_session,
    delete_lesson_session,
)

from ..modules.quiz import (
    generate_quiz,
    get_quiz,
    submit_quiz_answer,
    list_quiz_sessions,
    get_latest_quiz_for_session,
    rename_quiz_session,
    delete_quiz_session,
)
from ..modules.artifacts import (
    generate_card_quiz,
    generate_card_flashcards,
    get_artifact,
    update_artifact_meta,
    list_flashcard_sessions,
    get_latest_flashcard_artifact_for_session,
    rename_flashcard_session,
    delete_flashcard_session,
)
from ..modules.model_manager import get_active_model_profile_key, get_model_profiles, set_active_model_profile_key
from ..modules.notes import (
    delete_note as delete_user_note,
    get_note as get_user_note,
    list_notes as list_user_notes,
    save_note as save_user_note,
    update_note as update_user_note,
)
from ..modules.task_router import route_task
from ..modules.generator_executor import execute_generator_task, is_generator_task
from ..modules.utility_executor import execute_utility_task, is_utility_task

# ✅ Import Pydantic schemas for validation
from ..schemas.request import (
    LoginRequest, AskRequest, RenameSessionRequest, SetSessionContentRequest, ContextSelectionRequest,
    LessonPlanCreateRequest, LessonProgressRequest, QuizGenerateRequest,
    QuizSubmitRequest, FlashcardCreateRequest, ArtifactGenerateRequest, RegisterRequest, ResetPasswordRequest,
    ProfileUpdateRequest, SubscriptionQuoteRequest, SubscriptionActivateRequest,
    SubjectQuizRequest, QuestionPaperRequest, AssessmentAttemptRequest, LogActivityRequest,
    TranslateRequest, PreferencesUpdateRequest, AdminModelProfileUpdateRequest, NoteSaveRequest, NoteUpdateRequest,
    LinkStudentRequest, CollaborationNoteRequest, CollaborationNoteUpdateRequest, MentorAssignmentRequest,
    MentorAssignmentUpdateRequest, StudyPlanItemUpdateRequest,
)
from ..schemas.response import (
    LoginResponse, AskResponse, SessionListResponse, SessionContentResponse,
    ClassResponse, SubjectResponse, ContentsResponse, QuizResponse,
    LessonPlanResponse, ErrorResponse
)

router = APIRouter()
services = get_default_service_registry()

DEFAULT_REMINDER_SETTINGS = {
    "enabled": True,
    "frequency": "daily",
    "muted_ids": [],
}

router.include_router(flashcards_router)


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


@router.get("/health/runtime")
def runtime_health():
    """
    Lightweight runtime status endpoint used by frontend diagnostics.
    Kept unauthenticated so clients can detect backend reachability issues.
    """
    raw_mode = str(os.getenv("KB_REINDEX_MODE", "skip") or "skip").strip().lower()
    if str(os.getenv("SKIP_KB_REINDEX", "")).strip().lower() in {"1", "true", "yes", "on"}:
        raw_mode = "skip"
    if raw_mode in {"true", "1", "yes", "on", "changed"}:
        raw_mode = "incremental"
    elif raw_mode not in {"incremental", "full", "skip"}:
        raw_mode = "skip"

    return envelope(
        {
            "status": "ok",
            "api": "up",
            "ws": "configured",
            "kb_reindex_mode": raw_mode,
        },
        message_id="MSG-1000",
    )


def _get_user_row_by_email(email: str):
    return services.relationships.get_user_by_email(email)


def _resolve_student_user_id(student_identifier: str) -> Optional[str]:
    return services.relationships.resolve_student_user_id(student_identifier)


def _has_relationship_access(student_user_id: str, requester: dict) -> bool:
    return services.relationships.has_relationship_access(student_user_id, requester)

@router.post("/ask")
def ask(request: AskRequest, user=Depends(get_current_user)):
    """
    Protected Ask API
    - Requires JWT token
    - Supports session_id (optional)
    - Supports model selection via 'model_name' (optional)
    - Uses Redis cache for faster responses
    """

    query = request.query
    session_id = request.session_id
    model_name = request.model_name  # Optional model selection

    if not session_id:
        session_id = str(uuid.uuid4())

    routed_task = route_task(
        query=query,
        route="/ask",
        requested_task=request.task,
        model_name=model_name,
        content_id=request.content_id,
    )

    _consume_quota_or_raise(user, "ask")

    try:
        use_generator_executor = bool(request.task) or bool(routed_task.explicit) or routed_task.model_task == "summary"
        if is_utility_task(routed_task.model_task):
            ans = execute_utility_task(
                task=routed_task.model_task,
                query=query,
                user_id=user["username"],
                session_id=session_id,
                model_name=model_name,
                content_id=request.content_id,
            )
        elif is_generator_task(routed_task.model_task) and use_generator_executor:
            ans = execute_generator_task(
                task=routed_task.model_task,
                query=query,
                user_id=user["username"],
                session_id=session_id,
                model_name=model_name,
                content_id=request.content_id,
            )
        else:
            generate_kwargs = {
                "query": query,
                "user_id": user["username"],
                "session_id": session_id,
                "model_name": model_name,
                "session_content_override": request.content_id,
                "bypass_cache": request.bypass_cache,
            }
            if routed_task.model_task != "qa":
                generate_kwargs["task"] = routed_task.model_task

            ans = generate_answer(**generate_kwargs)
    except Exception:
        release_usage(user["username"], "ask")
        raise

    return envelope({
        "answer": ans,
        "session_id": session_id,
        "model_used": model_name if model_name else "default"
    }, message_id="MSG-1000")


def _start_admin_reindex_job(
    payload: Optional[dict],
    *,
    force_reindex: bool,
    requested_type: str,
):
    from ..modules.kb_sync import start_reindex_job

    payload = payload or {}
    target_path = None
    if isinstance(payload, dict):
        target_path = payload.get("path") or payload.get("relative_path") or payload.get("content_id")

    result = start_reindex_job(
        force_reindex=force_reindex,
        target_path=target_path,
        requested_type=requested_type,
    )
    response = {
        "status": result.get("status") or "started",
        "type": result.get("type") or requested_type,
        "job_id": result.get("job_id"),
    }
    if isinstance(result.get("reindex"), dict):
        response["reindex"] = result["reindex"]
    return envelope(response, message_id="MSG-1000")


@router.post("/admin/reindex")
def reindex(payload: Optional[dict] = Body(default=None), user=Depends(require_role("admin"))):
    payload = payload or {}
    requested_type = "file" if isinstance(payload, dict) and (payload.get("path") or payload.get("relative_path") or payload.get("content_id")) else "full"
    return _start_admin_reindex_job(payload, force_reindex=requested_type == "full", requested_type=requested_type)


@router.post("/admin/reindex/full")
def reindex_full(payload: Optional[dict] = Body(default=None), user=Depends(require_role("admin"))):
    return _start_admin_reindex_job(payload, force_reindex=True, requested_type="full")


@router.post("/admin/reindex-incremental")
def incremental_reindex(payload: Optional[dict] = Body(default=None), user=Depends(require_role("admin"))):
    return _start_admin_reindex_job(payload, force_reindex=False, requested_type="incremental")


@router.post("/admin/reindex/incremental")
def incremental_reindex_v2(payload: Optional[dict] = Body(default=None), user=Depends(require_role("admin"))):
    return _start_admin_reindex_job(payload, force_reindex=False, requested_type="incremental")


@router.post("/admin/reindex/file")
def file_reindex(payload: Optional[dict] = Body(default=None), user=Depends(require_role("admin"))):
    payload = payload or {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="A file path/content reference is required for file reindex.")

    file_id = payload.get("file_id")
    if file_id is not None:
        result = services.knowledge.queue_reindex(user, scope="file", file_id=int(file_id))
        return envelope(
            {
                "status": "started",
                "type": "file",
                "job_id": result.get("job_id"),
                "queued_files": result.get("queued_files", 0),
            },
            message_id="MSG-1000",
        )

    if not (payload.get("path") or payload.get("relative_path") or payload.get("content_id")):
        raise HTTPException(status_code=400, detail="A file path/content reference is required for file reindex.")
    return _start_admin_reindex_job(payload, force_reindex=False, requested_type="file")


@router.get("/admin/reindex-status")
def admin_reindex_status(user=Depends(require_role("admin"))):
    from ..modules.kb_sync import get_reindex_progress

    progress = get_reindex_progress()
    response = {
        "status": progress.get("status") or "idle",
        "type": progress.get("type") or progress.get("mode") or "idle",
        "job_id": progress.get("job_id"),
        "reindex": progress,
    }
    return envelope(response, message_id="MSG-1000")


@router.get("/admin/reindex/status/{job_id}")
def admin_reindex_status_by_job(job_id: str, user=Depends(require_role("admin"))):
    from ..modules.kb_sync import get_reindex_progress

    progress = get_reindex_progress(job_id)
    response = {
        "status": progress.get("status") or "idle",
        "type": progress.get("type") or progress.get("mode") or "unknown",
        "job_id": progress.get("job_id") or job_id,
        "reindex": progress,
    }
    return envelope(response, message_id="MSG-1000")


@router.get("/history")
def fetch_history(session_id: str, user=Depends(get_current_user)):
    """Return history; new sessions are valid and return an empty list."""
    _assert_session_owner_if_exists(session_id, user["username"])
    return envelope({"history": get_history(user["username"], session_id)}, message_id="MSG-1000")


@router.post("/login")
def login(request: LoginRequest, response: Response):
    """
    ✅ NOW WITH PYDANTIC VALIDATION
    Validates username and password fields
    """
    try:
        payload = services.identity.login(request.email, request.password, response)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    return envelope(payload, message_id="MSG-1000")


@router.get("/auth/session")
def get_auth_session(user=Depends(get_current_user)):
    """Return canonical authenticated user identity for cookie/bootstrap flows."""
    return envelope(services.identity.get_auth_session(user), message_id="MSG-1000")


@router.post("/logout")
def logout(response: Response):
    return envelope(services.identity.logout(response), message_id="MSG-1000")


@router.post("/register")
def register(request: RegisterRequest):
    """
    Register a new user account.
    Email is the unique user ID.
    """
    try:
        result = services.identity.register(
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            dob=request.dob,
            password=request.password,
            role=request.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return envelope(result, message_id="MSG-1000")


@router.post("/relationships/link-student")
def link_student(request: LinkStudentRequest, user=Depends(get_current_user)):
    requester_role = user.get("role", "student")
    if requester_role not in {"teacher", "parent"}:
        raise HTTPException(status_code=403, detail="Only teacher or parent accounts can link students")

    student = _get_user_row_by_email(request.student_email)
    if not student:
        raise HTTPException(status_code=404, detail="Student account not found")
    if student["role"] != "student":
        raise HTTPException(status_code=400, detail="Target user must have student role")

    services.relationships.link_student(
        student_user_id=student["username"],
        related_user_id=user["username"],
        relation_role=requester_role,
        relation_label=request.relation_label,
    )

    return envelope(
        {
            "status": "linked",
            "student_username": student["username"],
            "student_email": student["email"],
            "relation_role": requester_role,
            "relation_label": request.relation_label,
        },
        message_id="MSG-1000",
    )


@router.get("/relationships/my-students")
def my_students(user=Depends(get_current_user)):
    requester_role = user.get("role", "student")
    if requester_role not in {"teacher", "parent"}:
        raise HTTPException(status_code=403, detail="Only teacher or parent accounts can list linked students")

    students = services.relationships.list_students_for_related(user["username"], requester_role)
    return envelope({"students": students}, message_id="MSG-1000")


@router.get("/relationships/my-mentors")
def my_mentors(user=Depends(get_current_user)):
    if user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Only student accounts can list mentors")

    mentors = services.relationships.list_mentors_for_student(user["username"])
    return envelope({"mentors": mentors}, message_id="MSG-1000")


@router.post("/notes/save")
def save_summary_note(request: NoteSaveRequest, user=Depends(get_current_user)):
    note = save_user_note(
        user["username"],
        title=request.title,
        content=request.content,
        session_id=request.session_id,
        source_query=request.source_query,
        selected_content=request.selected_content,
        is_pinned=request.is_pinned,
    )
    return envelope({"status": "saved", "note": note}, message_id="MSG-1000")


@router.get("/notes")
def list_summary_notes(user=Depends(get_current_user)):
    return envelope({"notes": list_user_notes(user["username"])}, message_id="MSG-1000")


@router.get("/notes/{note_id}")
def get_summary_note(note_id: int, user=Depends(get_current_user)):
    note = get_user_note(user["username"], note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return envelope({"note": note}, message_id="MSG-1000")


@router.put("/notes/{note_id}")
def update_summary_note(note_id: int, request: NoteUpdateRequest, user=Depends(get_current_user)):
    note = update_user_note(
        user["username"],
        note_id,
        title=request.title,
        content=request.content,
        source_query=request.source_query,
        selected_content=request.selected_content,
        is_pinned=request.is_pinned,
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return envelope({"status": "updated", "note": note}, message_id="MSG-1000")


@router.delete("/notes/{note_id}")
def delete_summary_note(note_id: int, user=Depends(get_current_user)):
    deleted = delete_user_note(user["username"], note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return envelope({"status": "deleted", "note_id": note_id}, message_id="MSG-1000")


@router.get("/students/{student_username}/progress")
def get_student_progress(student_username: str, user=Depends(get_current_user)):
    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")
    dashboard, mastery = services.progress.get_student_progress(student_user_id)
    insights = services.progress.get_insights(student_user_id)
    study_plan = services.progress.get_study_plan(student_user_id)
    return envelope(
        {
            "student_username": student_user_id,
            "dashboard": dashboard,
            "mastery": mastery,
            "insights": insights,
            "study_plan": study_plan,
        },
        message_id="MSG-1000",
    )


@router.post("/collaboration/notes")
def add_collaboration_note(request: CollaborationNoteRequest, user=Depends(get_current_user)):
    role = user.get("role", "student")
    student_user_id = _resolve_student_user_id(request.student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if role not in {"teacher", "parent", "admin"}:
        raise HTTPException(status_code=403, detail="Only teacher, parent, or admin can add notes")
    if role != "admin" and not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    note_id = services.relationships.create_note(
        student_user_id=student_user_id,
        author_user_id=user["username"],
        author_role=role,
        note_text=request.note_text.strip(),
        visibility=request.visibility,
    )

    return envelope(
        {
            "status": "created",
            "note_id": note_id,
            "student_username": student_user_id,
            "visibility": request.visibility,
        },
        message_id="MSG-1000",
    )


@router.get("/students/{student_username}/notes")
def get_collaboration_notes(student_username: str, user=Depends(get_current_user)):
    role = user.get("role", "student")
    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    notes = services.relationships.list_notes(student_user_id, role, user["username"])
    return envelope({"student_username": student_user_id, "notes": notes}, message_id="MSG-1000")


@router.put("/students/{student_username}/notes/{note_id}")
def update_collaboration_note(
    student_username: str,
    note_id: int,
    request: CollaborationNoteUpdateRequest,
    user=Depends(get_current_user),
):
    role = user.get("role", "student")
    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if role not in {"teacher", "parent", "admin"}:
        raise HTTPException(status_code=403, detail="Only teacher, parent, or admin can update notes")
    if role != "admin" and not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    updated = services.relationships.update_note(
        student_user_id=student_user_id,
        note_id=note_id,
        updates=request.model_dump(exclude_none=True),
        requester_user_id=user["username"],
        requester_role=role,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Note not found")

    return envelope(updated, message_id="MSG-1000")


@router.delete("/students/{student_username}/notes/{note_id}")
def delete_collaboration_note(student_username: str, note_id: int, user=Depends(get_current_user)):
    role = user.get("role", "student")
    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if role not in {"teacher", "parent", "admin"}:
        raise HTTPException(status_code=403, detail="Only teacher, parent, or admin can delete notes")
    if role != "admin" and not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    deleted = services.relationships.delete_note(
        student_user_id=student_user_id,
        note_id=note_id,
        requester_user_id=user["username"],
        requester_role=role,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")

    return envelope(
        {
            "status": "deleted",
            "note_id": note_id,
            "student_username": student_user_id,
        },
        message_id="MSG-1000",
    )


@router.post("/students/{student_username}/assignments")
def create_student_assignment(student_username: str, request: MentorAssignmentRequest, user=Depends(get_current_user)):
    role = user.get("role", "student")
    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if role not in {"teacher", "parent", "admin"}:
        raise HTTPException(status_code=403, detail="Only teacher, parent, or admin can assign tasks")
    if role != "admin" and not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    assignment_id = services.relationships.create_assignment(
        student_user_id=student_user_id,
        author_user_id=user["username"],
        author_role=role,
        title=request.title.strip(),
        description=request.description.strip(),
        action_tab=request.action_tab,
        cta_label=(request.cta_label or "Open Assignment").strip(),
        chapter_hint=(request.chapter_hint or "").strip() or None,
        context_hint=(request.context_hint or request.description).strip(),
        due_label=(request.due_label or "").strip() or None,
    )

    return envelope(
        {
            "status": "created",
            "assignment_id": assignment_id,
            "student_username": student_user_id,
        },
        message_id="MSG-1000",
    )


@router.get("/students/{student_username}/assignments")
def get_student_assignments(student_username: str, user=Depends(get_current_user)):
    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    assignments = services.relationships.list_assignments(student_user_id)
    return envelope({"student_username": student_user_id, "assignments": assignments}, message_id="MSG-1000")


@router.put("/students/{student_username}/assignments/{assignment_id}")
def update_student_assignment(
    student_username: str,
    assignment_id: int,
    request: MentorAssignmentUpdateRequest,
    user=Depends(get_current_user),
):
    role = user.get("role", "student")
    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    updates = request.model_dump(exclude_unset=True)
    if role == "student":
        if set(updates.keys()) - {"status"}:
            raise HTTPException(status_code=403, detail="Students can only update assignment status")
    elif role not in {"teacher", "parent", "admin"}:
        raise HTTPException(status_code=403, detail="Only teacher, parent, or admin can update assignments")

    for field in ("title", "description", "chapter_hint", "context_hint"):
        if field in updates and isinstance(updates[field], str):
            updates[field] = updates[field].strip()
    if "cta_label" in updates and isinstance(updates["cta_label"], str):
        updates["cta_label"] = updates["cta_label"].strip() or "Open Assignment"
    if "due_label" in updates and isinstance(updates["due_label"], str):
        updates["due_label"] = updates["due_label"].strip() or None

    updated = services.relationships.update_assignment(student_user_id, assignment_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if role == "student" and updated.get("status") == "completed":
        _log_progress_activity_safe(
            user,
            updated.get("action_tab") or "other",
            subject=updated.get("chapter_hint") or updated.get("title") or "Assignment",
            chapter=updated.get("chapter_hint") or updated.get("title") or "Assignment",
            duration_seconds=300,
        )

    return envelope(updated, message_id="MSG-1000")


@router.delete("/students/{student_username}/assignments/{assignment_id}")
def delete_student_assignment(student_username: str, assignment_id: int, user=Depends(get_current_user)):
    role = user.get("role", "student")
    if role not in {"teacher", "parent", "admin"}:
        raise HTTPException(status_code=403, detail="Only teacher, parent, or admin can delete assignments")

    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if role != "admin" and not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    deleted = services.relationships.delete_assignment(student_user_id, assignment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Assignment not found")

    return envelope(
        {"status": "deleted", "assignment_id": assignment_id, "student_username": student_user_id},
        message_id="MSG-1000",
    )


@router.get("/profile")
def get_profile(user=Depends(get_current_user)):
    """Return the editable profile details for the current user."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT username, email, role, first_name, last_name, dob
            FROM users
            WHERE username = ?
            LIMIT 1
            """,
            (user["username"],),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")

    return envelope(
        {
            "profile": {
                "username": row[0],
                "email": row[1],
                "role": row[2],
                "first_name": row[3],
                "last_name": row[4],
                "dob": row[5],
            }
        },
        message_id="MSG-1000",
    )


@router.put("/profile")
def update_profile(request: ProfileUpdateRequest, user=Depends(get_current_user)):
    """Update mutable profile fields while keeping email immutable."""
    try:
        updated = services.identity.update_profile(
            username=user["username"],
            first_name=request.first_name,
            last_name=request.last_name,
            dob=request.dob,
            email=request.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return envelope({"profile": updated, "status": "updated"}, message_id="MSG-1000")


@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest):
    """
    Reset password using email + DOB match.
    """
    ok = services.identity.reset_password(
        email=request.email,
        dob=request.dob,
        new_password=request.new_password,
    )

    if not ok:
        raise HTTPException(status_code=400, detail="Invalid email or DOB")

    return envelope({"status": "password_reset"}, message_id="MSG-1000")


@router.get("/sessions")
def get_sessions(user=Depends(get_current_user)):
    """Return sessions with persisted titles."""
    return envelope({"sessions": services.learning.list_chat_sessions(user["username"])}, message_id="MSG-1000")


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, user=Depends(validate_session_ownership)):
    """✅ NOW WITH SESSION OWNERSHIP VALIDATION"""
    return envelope(services.learning.delete_chat_session(user["username"], session_id), message_id="MSG-1000")


@router.put("/sessions/{session_id}")
def rename_session(session_id: str, request: RenameSessionRequest, user=Depends(validate_session_ownership)):
    """
    ✅ NOW WITH SESSION OWNERSHIP VALIDATION
    Persistently rename a session
    """
    return envelope(services.learning.rename_chat_session(user["username"], session_id, request.title), message_id="MSG-1000")


@router.get("/sessions/{session_id}/content")
def get_session_content(session_id: str, user=Depends(get_current_user)):
    """Return session content; new sessions are valid and return null content."""
    _assert_session_owner_if_exists(session_id, user["username"])
    return envelope(services.learning.get_session_content(user, session_id), message_id="MSG-1000")


@router.put("/sessions/{session_id}/content")
def set_session_content(session_id: str, request: SetSessionContentRequest, user=Depends(get_current_user)):
    """
    Update session content path (PDF etc.).
    For new sessions with no history rows yet, return success without 404.
    """
    _assert_session_owner_if_exists(session_id, user["username"])
    return envelope(services.learning.set_session_content(user, session_id, request.content_id), message_id="MSG-1000")


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


@router.post("/files/upload")
async def upload_file(
    class_name: str = Form(...),
    subject_name: str = Form(...),
    folder_name: str = Form(...),
    display_name: str = Form(...),
    upload: UploadFile = File(...),
    user=Depends(get_current_user),
):
    _consume_quota_or_raise(user, "upload")
    try:
        result = upload_pdf(
            user=user,
            upload=upload,
            class_name=class_name,
            subject_name=subject_name,
            folder_name=folder_name,
            display_name=display_name,
        )
    except Exception:
        release_usage(user["username"], "upload")
        raise
    return envelope(result, message_id="MSG-1301")


@router.get("/files/tree")
def files_tree(user=Depends(get_current_user)):
    return envelope({"items": services.knowledge.file_tree(user)}, message_id="MSG-1000")


@router.get("/files/index-status")
def files_index_status(file_id: int | None = None, user=Depends(get_current_user)):
    return envelope({"items": services.knowledge.index_status(user, file_id=file_id)}, message_id="MSG-1000")


@router.post("/files/reindex")
def files_reindex(scope: str = Form("changed"), file_id: int | None = Form(None), user=Depends(get_current_user)):
    result = services.knowledge.queue_reindex(user, scope=scope, file_id=file_id)
    return envelope(result, message_id="MSG-1305")




def _kb_dir() -> str:
    """Return the absolute path to the knowledge_base directory."""
    return os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")), "knowledge_base")


@router.get("/pdf")
def serve_pdf(content_id: str | None = None, path: str | None = None, user=Depends(get_current_user)):
    """
    Serve PDF from knowledge base folder safely.
    Returns 403 on access violation (never 200).
    """
    reference = unquote(content_id or path or "")
    if not reference:
        raise HTTPException(status_code=400, detail="Content reference is required")

    try:
        resolved = resolve_content_reference(user, reference)
    except HTTPException as exc:
        if path and not content_id and exc.status_code == 400:
            raise HTTPException(status_code=403, detail="Access denied")
        raise

    full_path = resolved["path"] if resolved else None

    if not full_path or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(full_path, media_type="application/pdf")


# 🔹 Knowledge Base Endpoints (all require authentication)
@router.get("/classes")
def get_classes(user=Depends(get_current_user)):
    return envelope({"classes": services.knowledge.list_classes()}, message_id="MSG-1000")


@router.get("/subjects")
def get_subjects(class_name: str, user=Depends(get_current_user)):
    try:
        subjects = services.knowledge.list_subjects(class_name)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path component")
    return envelope({"subjects": subjects}, message_id="MSG-1000")


@router.get("/folders")
def get_folders(class_name: str, subject: str, user=Depends(get_current_user)):
    try:
        folders = services.knowledge.list_folders(class_name, subject)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path component")
    return envelope({"folders": folders}, message_id="MSG-1000")


@router.get("/contents")
def get_contents(class_name: str, subject: str, folder: str, user=Depends(get_current_user)):
    try:
        contents = services.knowledge.list_contents(class_name, subject, folder)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path component")
    return envelope({"contents": contents}, message_id="MSG-1000")

@router.post("/lesson-plan/create")
def create_plan(request: LessonPlanCreateRequest, user=Depends(get_current_user)):
    """✅ NOW WITH PYDANTIC VALIDATION"""
    _consume_quota_or_raise(user, "lesson")
    try:
        plan = generate_lesson_plan(
            user["username"],
            request.session_id,
            request.chapter,
            lesson_context=request.lesson_context,
            selected_content=request.content_id,
            requested_by=user,
        )
    except Exception:
        release_usage(user["username"], "lesson")
        raise

    _log_progress_activity_safe(
        user,
        "lesson",
        subject=request.chapter,
        chapter=request.chapter,
        duration_seconds=60,
    )
    return envelope(plan, message_id="MSG-1000")


@router.get("/lesson-plan/sessions")
def get_lesson_sessions(user=Depends(get_current_user)):
    """Return saved lesson-plan sessions for the current user."""
    return envelope({"sessions": services.learning.list_lesson_sessions(user["username"])}, message_id="MSG-1000")


@router.put("/lesson-plan/sessions/{session_id}")
def rename_lesson_plan_session(session_id: str, request: RenameSessionRequest, user=Depends(get_current_user)):
    """Rename a lesson-plan session for the current user."""
    result = services.learning.rename_lesson_session(user["username"], session_id, request.title)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Lesson session not found")
    return envelope(result, message_id="MSG-1000")


@router.delete("/lesson-plan/sessions/{session_id}")
def remove_lesson_plan_session(session_id: str, user=Depends(get_current_user)):
    """Delete a lesson-plan session for the current user."""
    result = services.learning.delete_lesson_session(user["username"], session_id)
    return envelope(result, message_id="MSG-1000")


@router.get("/lesson-plan")
def fetch_plan(session_id: str, user=Depends(get_current_user)):
    """Get lesson plan for a session"""
    plan = get_lesson_plan(user["username"], session_id)
    return envelope(plan or {}, message_id="MSG-1000")


@router.post("/lesson-plan/progress")
def update_progress(request: LessonProgressRequest, user=Depends(get_current_user)):
    """✅ NOW WITH PYDANTIC VALIDATION"""
    result = update_step_progress(
        user["username"],
        request.session_id,
        request.step_id,
        request.status
    )
    return envelope(result, message_id="MSG-1000")


@router.get("/lesson-plan/next")
def next_step(session_id: str, user=Depends(get_current_user)):
    """Get next lesson step"""
    nxt = get_next_step(user["username"], session_id)
    return envelope({"next_step": nxt}, message_id="MSG-1000")



# -------------------------
# Quiz Endpoints
# -------------------------

@router.post("/quiz/generate")
def api_generate_quiz(request: QuizGenerateRequest, user=Depends(get_current_user)):
    """
    ✅ NOW WITH PYDANTIC VALIDATION
    Generate quiz for a chapter
    """
    _consume_quota_or_raise(user, "quiz")
    try:
        quiz_data = generate_quiz(
            user["username"],
            request.session_id,
            request.chapter,
            context_hint=request.quiz_context,
            selected_content=request.content_id,
            requested_by=user,
        )
    except Exception:
        release_usage(user["username"], "quiz")
        raise

    _log_progress_activity_safe(
        user,
        "quiz",
        subject=request.chapter,
        chapter=request.chapter,
        duration_seconds=60,
    )
    return envelope({"quiz_id": quiz_data["quiz_id"], "quiz": quiz_data["questions"]}, message_id="MSG-1000")


@router.get("/plan/me")
def get_my_plan(user=Depends(get_current_user)):
    return envelope(services.commercial.get_plan_me(user["username"]), message_id="MSG-1000")


@router.get("/plan/limits")
def get_plan_limits(user=Depends(get_current_user)):
    return envelope(services.commercial.get_plan_limits(user["username"]), message_id="MSG-1000")


@router.get("/subscription/catalog")
def get_subscription_catalog_endpoint(user=Depends(get_current_user)):
    return envelope(services.commercial.get_subscription_catalog(), message_id="MSG-1000")


@router.post("/subscription/quote")
def get_subscription_quote(request: SubscriptionQuoteRequest, user=Depends(get_current_user)):
    quote = services.commercial.quote_subscription(
        class_names=request.class_names,
        promo_code=request.promo_code,
        auto_renew=request.auto_renew,
    )
    return envelope(quote, message_id="MSG-1000")


@router.post("/subscription/activate")
def activate_subscription_endpoint(request: SubscriptionActivateRequest, user=Depends(get_current_user)):
    result = services.commercial.activate_subscription(
        user_id=user["username"],
        class_names=request.class_names,
        promo_code=request.promo_code,
        auto_renew=request.auto_renew,
        payment_reference=request.payment_reference,
    )
    return envelope(result, message_id="MSG-1000")


@router.get("/lesson-plan/{lesson_plan_id}/cards")
def lesson_cards(lesson_plan_id: int, user=Depends(get_current_user)):
    cards = get_lesson_plan_cards(user["username"], lesson_plan_id)
    if not cards:
        raise HTTPException(status_code=404, detail="Lesson cards not found")
    return envelope({"lesson_plan_id": lesson_plan_id, "cards": cards}, message_id="MSG-1000")


@router.post("/lesson-plan/{lesson_plan_id}/cards/{card_id}/complete")
def complete_card(lesson_plan_id: int, card_id: int, user=Depends(get_current_user)):
    result = complete_lesson_card(user["username"], lesson_plan_id, card_id, status="completed")
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Lesson card not found")

    _log_progress_activity_safe(user, "lesson", duration_seconds=300)
    return envelope(result, message_id="MSG-1000")


@router.put("/quiz/sessions/{session_id}")
def rename_quiz_session_endpoint(session_id: str, request: RenameSessionRequest, user=Depends(get_current_user)):
    result = services.learning.rename_quiz_session(user["username"], session_id, request.title)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Quiz session not found")
    return envelope(result, message_id="MSG-1000")


@router.delete("/quiz/sessions/{session_id}")
def delete_quiz_session_endpoint(session_id: str, user=Depends(get_current_user)):
    result = services.learning.delete_quiz_session(user["username"], session_id)
    return envelope(result, message_id="MSG-1000")


@router.post("/cards/{card_id}/quiz/generate")
def generate_card_quiz_endpoint(
    card_id: int,
    request: ArtifactGenerateRequest | None = Body(default=None),
    user=Depends(get_current_user),
):
    card = get_card_for_user(user["username"], card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    _consume_quota_or_raise(user, "quiz")
    try:
        result = generate_card_quiz(
            user["username"],
            card,
            context_hint=request.context if request else None,
            selected_content=request.content_id if request else None,
        )
    except Exception:
        release_usage(user["username"], "quiz")
        raise

    _log_progress_activity_safe(
        user,
        "quiz",
        subject=card.get("title", ""),
        chapter=card.get("title", ""),
        duration_seconds=120,
    )
    return envelope(result, message_id="MSG-1000")


@router.post("/cards/{card_id}/flashcards/generate")
def generate_card_flashcards_endpoint(
    card_id: int,
    request: ArtifactGenerateRequest | None = Body(default=None),
    user=Depends(get_current_user),
):
    card = get_card_for_user(user["username"], card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    _consume_quota_or_raise(user, "flashcard")
    try:
        result = generate_card_flashcards(
            user["username"],
            card,
            context_hint=request.context if request else None,
            selected_content=request.content_id if request else None,
        )
    except Exception:
        release_usage(user["username"], "flashcard")
        raise

    _log_progress_activity_safe(
        user,
        "flashcard",
        subject=card.get("title", ""),
        chapter=card.get("title", ""),
        duration_seconds=120,
    )
    return envelope(result, message_id="MSG-1000")


@router.get("/artifacts/{artifact_id}")
def get_artifact_endpoint(artifact_id: int, user=Depends(get_current_user)):
    artifact = get_artifact(user["username"], artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return envelope({"artifact": artifact}, message_id="MSG-1000")


@router.post("/artifacts/{artifact_id}/save")
def save_artifact_endpoint(
    artifact_id: int,
    title: str | None = Form(None),
    tags: str | None = Form(None),
    user=Depends(get_current_user),
):
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    ok = update_artifact_meta(user["username"], artifact_id, title=title, tags=tag_list)
    if not ok:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return envelope({"artifact_id": artifact_id, "status": "saved"}, message_id="MSG-1000")


@router.get("/quiz/sessions")
def api_list_quiz_sessions(user=Depends(get_current_user)):
    """Return saved quiz sessions for the current user."""
    return envelope({"sessions": services.learning.list_quiz_sessions(user["username"])}, message_id="MSG-1000")


@router.get("/flashcards/sessions")
def api_list_flashcard_sessions(user=Depends(get_current_user)):
    """Return saved flashcard sessions for the current user."""
    return envelope({"sessions": services.learning.list_flashcard_sessions(user["username"])}, message_id="MSG-1000")


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


@router.get("/quiz/latest")
def api_get_latest_quiz(session_id: str, user=Depends(get_current_user)):
    """Retrieve the latest quiz generated for a session."""
    quiz = services.learning.get_latest_quiz(user["username"], session_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return envelope({"quiz_id": quiz["quiz_id"], "quiz": quiz["questions"]}, message_id="MSG-1000")


@router.get("/quiz/{quiz_id}")
def api_get_quiz(quiz_id: str, session_id: str, user=Depends(get_current_user)):
    """Retrieve a specific quiz"""
    quiz = get_quiz(user["username"], session_id, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return envelope({"quiz_id": quiz["quiz_id"], "quiz": quiz["questions"]}, message_id="MSG-1000")


@router.post("/quiz/{quiz_id}/submit")
def api_submit_quiz(quiz_id: str, request: QuizSubmitRequest, user=Depends(get_current_user)):
    """Submit answers for a quiz and update mastery scores."""
    result = submit_quiz_answer(user["username"], request.session_id, quiz_id, request.answers)

    # Update mastery scores based on quiz results
    if result:
        correct = sum(1 for v in result.values() if v.get("is_correct"))
        total = len(result)
        subject, chapter = _infer_subject_chapter(user["username"], request.session_id)
        if total > 0:
            try:
                new_mastery = services.progress.update_mastery(
                    user["username"],
                    subject,
                    chapter,
                    correct,
                    total,
                )
                result["_mastery_pct"] = new_mastery
            except Exception:
                pass

        _log_progress_activity_safe(
            user,
            "quiz",
            subject=subject,
            chapter=chapter,
            duration_seconds=max(60, total * 45),
        )

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
# Assessment: subject quiz + question papers
# ---------------------------------------------------------------------------

@router.post("/assessment/subject-quiz")
def api_generate_subject_quiz(request: SubjectQuizRequest, user=Depends(get_current_user)):
    """Generate a cross-chapter subject-level quiz (practice or exam mode)."""
    _consume_quota_or_raise(user, "quiz")
    try:
        result = generate_subject_quiz(
            user_id=user["username"],
            session_id=request.session_id,
            subject=request.subject,
            class_name=request.class_name,
            num_questions=request.num_questions,
            difficulty=request.difficulty,
            mode=request.mode,
        )
    except Exception:
        release_usage(user["username"], "quiz")
        raise

    _log_progress_activity_safe(
        user,
        "assessment",
        subject=request.subject,
        chapter=request.subject,
        duration_seconds=120,
    )
    return envelope(result, message_id="MSG-1000")


@router.post("/assessment/question-paper")
def api_generate_question_paper(request: QuestionPaperRequest, user=Depends(get_current_user)):
    """Generate a structured question paper with sections and marks."""
    _consume_quota_or_raise(user, "quiz")
    try:
        result = generate_question_paper(
            user_id=user["username"],
            session_id=request.session_id,
            subject=request.subject,
            class_name=request.class_name,
            total_marks=request.total_marks,
            difficulty=request.difficulty,
            sections_config=request.sections,
        )
    except Exception:
        release_usage(user["username"], "quiz")
        raise

    _log_progress_activity_safe(
        user,
        "assessment",
        subject=request.subject,
        chapter=request.subject,
        duration_seconds=120,
    )
    return envelope(result, message_id="MSG-1000")


@router.get("/assessment/papers")
def api_list_assessment_papers(
    paper_type: Optional[str] = None,
    user=Depends(get_current_user),
):
    """List all assessment papers for the current user (newest first)."""
    papers = list_assessment_papers(user["username"], paper_type=paper_type)
    return envelope({"papers": papers}, message_id="MSG-1000")


@router.get("/assessment/papers/{paper_id}")
def api_get_assessment_paper(paper_id: int, user=Depends(get_current_user)):
    """Retrieve a specific assessment paper by ID."""
    paper = get_assessment_paper(user["username"], paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Assessment paper not found")
    return envelope({"paper": paper}, message_id="MSG-1000")


@router.post("/assessment/papers/{paper_id}/attempt")
def api_record_assessment_attempt(
    paper_id: int,
    request: AssessmentAttemptRequest,
    user=Depends(get_current_user),
):
    """Save a completed assessment attempt for later history review."""
    result = record_assessment_attempt(
        user_id=user["username"],
        paper_id=paper_id,
        correct_count=request.correct_count,
        total_questions=request.total_questions,
        score_pct=request.score_pct,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Assessment paper not found")

    _log_progress_activity_safe(
        user,
        "assessment",
        subject=result.get("subject", ""),
        chapter=result.get("subject", ""),
        duration_seconds=max(60, request.total_questions * 30),
    )
    return envelope(
        {
            "saved": True,
            "attempt_summary": {
                "attempt_count": result["attempt_count"],
                "best_score_pct": result["best_score_pct"],
                "last_score_pct": result["last_score_pct"],
                "last_attempted_at": result.get("last_attempted_at"),
                "recent_scores": result.get("recent_scores") or [],
            },
        },
        message_id="MSG-1000",
    )


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
