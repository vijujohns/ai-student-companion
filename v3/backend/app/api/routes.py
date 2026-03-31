"""
REST APIs
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Response, UploadFile, File, Form
from ..modules.rag import generate_answer
from ..modules.history import get_history
from ..modules.auth import authenticate_user, clear_auth_cookie, create_access_token, set_auth_cookie
from ..modules.user_manager import register_user, reset_password_with_email_dob
from ..modules.user_manager import update_user_profile
from ..modules.db import get_connection
from ..modules.dependencies import require_role, get_current_user, validate_session_ownership, require_quota
from ..modules.messages import envelope
from ..modules.policy import increment_usage, get_user_plan, get_usage_snapshot, PLAN_LIMITS
from ..modules.file_management import (
    get_files_tree,
    get_index_status,
    make_kb_content_ref,
    queue_reindex,
    resolve_content_reference,
    upload_pdf,
)
import uuid
from fastapi.responses import FileResponse
from urllib.parse import unquote
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

# ✅ Import Pydantic schemas for validation
from ..schemas.request import (
    LoginRequest, AskRequest, RenameSessionRequest, SetSessionContentRequest,
    LessonPlanCreateRequest, LessonProgressRequest, QuizGenerateRequest,
    QuizSubmitRequest, FlashcardCreateRequest, ArtifactGenerateRequest, RegisterRequest, ResetPasswordRequest,
    ProfileUpdateRequest,
)
from ..schemas.response import (
    LoginResponse, AskResponse, SessionListResponse, SessionContentResponse,
    ClassResponse, SubjectResponse, ContentsResponse, QuizResponse,
    LessonPlanResponse, ErrorResponse
)

router = APIRouter()

router.include_router(flashcards_router)


def _assert_session_owner_if_exists(session_id: str, username: str) -> None:
    """Allow empty/new sessions, but block access to sessions owned by others."""
    from ..modules.db import get_connection

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id FROM chat_history WHERE session_id = ? LIMIT 1",
        (session_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row and row[0] != username:
        raise HTTPException(status_code=403, detail="You do not have access to this session")

@router.post("/ask")
def ask(request: AskRequest, user=Depends(require_quota("ask"))):
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

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_content FROM chat_history
        WHERE user_id=? AND session_id=?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user["username"], session_id),
    )
    row = cursor.fetchone()
    conn.close()
    session_content_path = row[0] if row else None

    # 🔹 Generate answer via RAG pipeline (handles caching internally)
    ans = generate_answer(
        query=query,
        user_id=user["username"],
        session_id=session_id,
        model_name=model_name  # Pass optional model selection
    )
    increment_usage(user["username"], "ask")

    return envelope({
        "answer": ans,
        "session_id": session_id,
        "model_used": model_name if model_name else "default"
    }, message_id="MSG-1000")


@router.post("/admin/reindex")
def reindex(user=Depends(require_role("admin"))):
    from ..modules.faiss_store import load_knowledge_base

    load_knowledge_base(force_reindex=True)
    return envelope({"status": "Reindex completed"}, message_id="MSG-1000")


@router.post("/admin/reindex-incremental")
def incremental_reindex(user=Depends(require_role("admin"))):
    from ..modules.faiss_store import load_knowledge_base
    load_knowledge_base(force_reindex=False)
    return envelope({"status": "Incremental reindex completed"}, message_id="MSG-1000")


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
    user = authenticate_user(request.email, request.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user)
    set_auth_cookie(response, token)

    return envelope({
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"],
        "username": user["username"],
        "email": user.get("email")
    }, message_id="MSG-1000")


@router.get("/auth/session")
def get_auth_session(user=Depends(get_current_user)):
    """Return canonical authenticated user identity for cookie/bootstrap flows."""
    return envelope(
        {
            "authenticated": True,
            "username": user["username"],
            "email": user.get("email") or user["username"],
            "role": user.get("role", "user"),
        },
        message_id="MSG-1000",
    )


@router.post("/logout")
def logout(response: Response):
    clear_auth_cookie(response)
    return envelope({"status": "logged_out"}, message_id="MSG-1000")


@router.post("/register")
def register(request: RegisterRequest):
    """
    Register a new user account.
    Email is the unique user ID.
    """
    conn = get_connection()
    try:
        user = register_user(
            db_connection=conn,
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            dob=request.dob,
            password=request.password,
            role="student",
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    finally:
        conn.close()

    return envelope({
        "status": "registered",
        "email": user["email"],
    }, message_id="MSG-1000")


@router.put("/profile")
def update_profile(request: ProfileUpdateRequest, user=Depends(get_current_user)):
    """Update mutable profile fields while keeping email immutable."""
    conn = get_connection()
    try:
        updated = update_user_profile(
            db_connection=conn,
            username=user["username"],
            first_name=request.first_name,
            last_name=request.last_name,
            dob=request.dob,
            email=request.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        conn.close()

    return envelope({"profile": updated, "status": "updated"}, message_id="MSG-1000")


@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest):
    """
    Reset password using email + DOB match.
    """
    conn = get_connection()
    try:
        ok = reset_password_with_email_dob(
            db_connection=conn,
            email=request.email,
            dob=request.dob,
            new_password=request.new_password,
        )
    finally:
        conn.close()

    if not ok:
        raise HTTPException(status_code=400, detail="Invalid email or DOB")

    return envelope({"status": "password_reset"}, message_id="MSG-1000")


@router.get("/sessions")
def get_sessions(user=Depends(get_current_user)):
    """
    Return sessions with persisted titles
    """
    from ..modules.db import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT 
        session_id,
        MAX(session_title),
        MAX(timestamp),
        MAX(selected_content)
    FROM chat_history
    WHERE user_id=?
    GROUP BY session_id
    ORDER BY MAX(timestamp) DESC
    """, (user["username"],))

    rows = cursor.fetchall()
    conn.close()

    sessions = [
        {
            "id": r[0],
            "title": r[1] if r[1] else "New Chat",
            "last_updated": r[2],
            "selected_content": r[3]
        }
        for r in rows
    ]
    return envelope({"sessions": sessions}, message_id="MSG-1000")


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, user=Depends(validate_session_ownership)):
    """✅ NOW WITH SESSION OWNERSHIP VALIDATION"""
    from ..modules.db import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM chat_history
    WHERE user_id=? AND session_id=?
    """, (user["username"], session_id))

    conn.commit()
    conn.close()

    return envelope({"status": "deleted"}, message_id="MSG-1000")


@router.put("/sessions/{session_id}")
def rename_session(session_id: str, request: RenameSessionRequest, user=Depends(validate_session_ownership)):
    """
    ✅ NOW WITH SESSION OWNERSHIP VALIDATION
    Persistently rename a session
    """
    from ..modules.db import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE chat_history
    SET session_title=?
    WHERE user_id=? AND session_id=?
    """, (request.title, user["username"], session_id))

    conn.commit()
    conn.close()

    return envelope({"status": "updated"}, message_id="MSG-1000")


@router.get("/sessions/{session_id}/content")
def get_session_content(session_id: str, user=Depends(get_current_user)):
    """Return session content; new sessions are valid and return null content."""
    _assert_session_owner_if_exists(session_id, user["username"])
    from ..modules.db import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT session_content FROM chat_history
        WHERE user_id=? AND session_id=?
        ORDER BY id DESC
        LIMIT 1
    """, (user["username"], session_id))
    row = cursor.fetchone()
    conn.close()
    session_content = row[0] if row else None
    if session_content:
        try:
            resolved = resolve_content_reference(user, session_content)
            session_content = resolved["content_id"] if resolved else None
        except HTTPException:
            session_content = None
    return envelope({"session_content": session_content}, message_id="MSG-1000")


@router.put("/sessions/{session_id}/content")
def set_session_content(session_id: str, request: SetSessionContentRequest, user=Depends(get_current_user)):
    """
    Update session content path (PDF etc.).
    For new sessions with no history rows yet, return success without 404.
    """
    _assert_session_owner_if_exists(session_id, user["username"])
    resolved = resolve_content_reference(user, request.content_id or request.path)
    canonical_content_id = resolved["content_id"] if resolved else None
    from ..modules.db import get_connection
    conn = get_connection()
    cursor = conn.cursor()

    # Update all future chats for this session with new content
    cursor.execute("""
        UPDATE chat_history
        SET session_content=?
        WHERE user_id=? AND session_id=? AND session_content IS NULL
    """, (canonical_content_id, user["username"], session_id))

    conn.commit()
    conn.close()
    return envelope({"status": "updated", "session_content": canonical_content_id}, message_id="MSG-1000")


@router.post("/files/upload")
async def upload_file(
    class_name: str = Form(...),
    subject_name: str = Form(...),
    folder_name: str = Form(...),
    display_name: str = Form(...),
    upload: UploadFile = File(...),
    user=Depends(require_quota("upload")),
):
    result = upload_pdf(
        user=user,
        upload=upload,
        class_name=class_name,
        subject_name=subject_name,
        folder_name=folder_name,
        display_name=display_name,
    )
    increment_usage(user["username"], "upload")
    return envelope(result, message_id="MSG-1301")


@router.get("/files/tree")
def files_tree(user=Depends(get_current_user)):
    return envelope({"items": get_files_tree(user)}, message_id="MSG-1000")


@router.get("/files/index-status")
def files_index_status(file_id: int | None = None, user=Depends(get_current_user)):
    return envelope({"items": get_index_status(user, file_id=file_id)}, message_id="MSG-1000")


@router.post("/files/reindex")
def files_reindex(scope: str = Form("changed"), file_id: int | None = Form(None), user=Depends(get_current_user)):
    result = queue_reindex(user, scope=scope, file_id=file_id)
    return envelope(result, message_id="MSG-1305")


def _kb_dir() -> str:
    return os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")), "knowledge_base")


def _safe_kb_path(*parts: str) -> str:
    """
    Securely join path components under the knowledge_base directory.
    Raises HTTPException 400 if any component attempts directory traversal.
    """
    kb = _kb_dir()
    # Reject any component containing path separators or parent references
    for part in parts:
        if not part or "." in part.split(os.sep) or any(c in part for c in ("/", "\\", ".." )):
            raise HTTPException(status_code=400, detail="Invalid path component")
    candidate = os.path.abspath(os.path.join(kb, *parts))
    if not candidate.startswith(kb + os.sep) and candidate != kb:
        raise HTTPException(status_code=400, detail="Invalid path component")
    return candidate


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
    KB_DIR = _kb_dir()
    if not os.path.exists(KB_DIR):
        return envelope({"classes": []}, message_id="MSG-1000")
    classes = sorted([d for d in os.listdir(KB_DIR) if os.path.isdir(os.path.join(KB_DIR, d))])
    return envelope({"classes": classes}, message_id="MSG-1000")


@router.get("/subjects")
def get_subjects(class_name: str, user=Depends(get_current_user)):
    class_path = _safe_kb_path(class_name)
    if not os.path.exists(class_path):
        return envelope({"subjects": []}, message_id="MSG-1000")
    subjects = sorted([d for d in os.listdir(class_path) if os.path.isdir(os.path.join(class_path, d))])
    return envelope({"subjects": subjects}, message_id="MSG-1000")


@router.get("/folders")
def get_folders(class_name: str, subject: str, user=Depends(get_current_user)):
    subject_path = _safe_kb_path(class_name, subject)
    if not os.path.exists(subject_path):
        return envelope({"folders": []}, message_id="MSG-1000")
    folders = sorted([d for d in os.listdir(subject_path) if os.path.isdir(os.path.join(subject_path, d))])
    return envelope({"folders": folders}, message_id="MSG-1000")


@router.get("/contents")
def get_contents(class_name: str, subject: str, folder: str, user=Depends(get_current_user)):
    folder_path = _safe_kb_path(class_name, subject, folder)
    if not os.path.exists(folder_path):
        return envelope({"contents": []}, message_id="MSG-1000")

    contents = []
    for f in os.listdir(folder_path):
        full_path = os.path.join(folder_path, f)
        if os.path.isfile(full_path) and f.lower().endswith(".pdf"):
            relative_path = os.path.relpath(full_path, _kb_dir())
            contents.append({"title": os.path.splitext(f)[0], "content_id": make_kb_content_ref(relative_path)})
    return envelope({"contents": contents}, message_id="MSG-1000")

@router.post("/lesson-plan/create")
def create_plan(request: LessonPlanCreateRequest, user=Depends(require_quota("lesson"))):
    """✅ NOW WITH PYDANTIC VALIDATION"""
    plan = generate_lesson_plan(
        user["username"],
        request.session_id,
        request.chapter,
        lesson_context=request.lesson_context,
    )
    increment_usage(user["username"], "lesson")
    return envelope(plan, message_id="MSG-1000")


@router.get("/lesson-plan/sessions")
def get_lesson_sessions(user=Depends(get_current_user)):
    """Return saved lesson-plan sessions for the current user."""
    return envelope({"sessions": list_lesson_sessions(user["username"])}, message_id="MSG-1000")


@router.put("/lesson-plan/sessions/{session_id}")
def rename_lesson_plan_session(session_id: str, request: RenameSessionRequest, user=Depends(get_current_user)):
    """Rename a lesson-plan session for the current user."""
    result = rename_lesson_session(user["username"], session_id, request.title)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Lesson session not found")
    return envelope(result, message_id="MSG-1000")


@router.delete("/lesson-plan/sessions/{session_id}")
def remove_lesson_plan_session(session_id: str, user=Depends(get_current_user)):
    """Delete a lesson-plan session for the current user."""
    result = delete_lesson_session(user["username"], session_id)
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
def api_generate_quiz(request: QuizGenerateRequest, user=Depends(require_quota("quiz"))):
    """
    ✅ NOW WITH PYDANTIC VALIDATION
    Generate quiz for a chapter
    """
    quiz_data = generate_quiz(
        user["username"],
        request.session_id,
        request.chapter,
        context_hint=request.quiz_context,
    )
    increment_usage(user["username"], "quiz")
    return envelope({"quiz_id": quiz_data["quiz_id"], "quiz": quiz_data["questions"]}, message_id="MSG-1000")


@router.get("/plan/me")
def get_my_plan(user=Depends(get_current_user)):
    plan = get_user_plan(user["username"])
    usage = get_usage_snapshot(user["username"])
    return envelope({"plan": plan, "usage": usage}, message_id="MSG-1000")


@router.get("/plan/limits")
def get_plan_limits(user=Depends(get_current_user)):
    current = get_user_plan(user["username"])
    return envelope(
        {
            "plan_code": current["plan_code"],
            "effective_limits": current["limits"],
            "all_limits": PLAN_LIMITS,
        },
        message_id="MSG-1000",
    )


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
    return envelope(result, message_id="MSG-1000")


@router.put("/quiz/sessions/{session_id}")
def rename_quiz_session_endpoint(session_id: str, request: RenameSessionRequest, user=Depends(get_current_user)):
    result = rename_quiz_session(user["username"], session_id, request.title)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Quiz session not found")
    return envelope(result, message_id="MSG-1000")


@router.delete("/quiz/sessions/{session_id}")
def delete_quiz_session_endpoint(session_id: str, user=Depends(get_current_user)):
    result = delete_quiz_session(user["username"], session_id)
    return envelope(result, message_id="MSG-1000")


@router.post("/cards/{card_id}/quiz/generate")
def generate_card_quiz_endpoint(
    card_id: int,
    request: ArtifactGenerateRequest | None = Body(default=None),
    user=Depends(require_quota("quiz")),
):
    card = get_card_for_user(user["username"], card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    result = generate_card_quiz(user["username"], card, context_hint=request.context if request else None)
    increment_usage(user["username"], "quiz")
    return envelope(result, message_id="MSG-1000")


@router.post("/cards/{card_id}/flashcards/generate")
def generate_card_flashcards_endpoint(
    card_id: int,
    request: ArtifactGenerateRequest | None = Body(default=None),
    user=Depends(require_quota("flashcard")),
):
    card = get_card_for_user(user["username"], card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    result = generate_card_flashcards(user["username"], card, context_hint=request.context if request else None)
    increment_usage(user["username"], "flashcard")
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
    return envelope({"sessions": list_quiz_sessions(user["username"])}, message_id="MSG-1000")


@router.get("/flashcards/sessions")
def api_list_flashcard_sessions(user=Depends(get_current_user)):
    """Return saved flashcard sessions for the current user."""
    return envelope({"sessions": list_flashcard_sessions(user["username"])}, message_id="MSG-1000")


@router.get("/flashcards/latest")
def api_get_latest_flashcards(session_id: str, user=Depends(get_current_user)):
    artifact = get_latest_flashcard_artifact_for_session(user["username"], session_id)
    if not artifact:
        return envelope({"error": "Flashcards not found"}, message_id="MSG-1000")
    return envelope({"artifact": artifact}, message_id="MSG-1000")


@router.put("/flashcards/sessions/{session_id}")
def rename_flashcard_session_endpoint(session_id: str, request: RenameSessionRequest, user=Depends(get_current_user)):
    result = rename_flashcard_session(user["username"], session_id, request.title)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Flashcard session not found")
    return envelope(result, message_id="MSG-1000")


@router.delete("/flashcards/sessions/{session_id}")
def delete_flashcard_session_endpoint(session_id: str, user=Depends(get_current_user)):
    result = delete_flashcard_session(user["username"], session_id)
    return envelope(result, message_id="MSG-1000")


@router.get("/quiz/latest")
def api_get_latest_quiz(session_id: str, user=Depends(get_current_user)):
    """Retrieve the latest quiz generated for a session."""
    quiz = get_latest_quiz_for_session(user["username"], session_id)
    if not quiz:
        return envelope({"error": "Quiz not found"}, message_id="MSG-1000")
    return envelope({"quiz_id": quiz["quiz_id"], "quiz": quiz["questions"]}, message_id="MSG-1000")


@router.get("/quiz/{quiz_id}")
def api_get_quiz(quiz_id: str, session_id: str, user=Depends(get_current_user)):
    """Retrieve a specific quiz"""
    quiz = get_quiz(user["username"], session_id, quiz_id)
    if not quiz:
        return envelope({"error": "Quiz not found"}, message_id="MSG-1000")
    return envelope({"quiz_id": quiz["quiz_id"], "quiz": quiz["questions"]}, message_id="MSG-1000")


@router.post("/quiz/{quiz_id}/submit")
def api_submit_quiz(quiz_id: str, request: QuizSubmitRequest, user=Depends(get_current_user)):
    """
    ✅ NOW WITH PYDANTIC VALIDATION
    Submit answers for a quiz.
    """
    result = submit_quiz_answer(user["username"], request.session_id, quiz_id, request.answers)
    return envelope(result, message_id="MSG-1000")