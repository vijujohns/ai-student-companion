from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from ..modules.artifacts import (
    generate_card_flashcards,
    generate_card_quiz,
)
from ..modules.dependencies import get_current_user
from ..modules.lesson_plan import get_card_for_user
from ..modules.messages import envelope
from ..modules.policy import release_usage
from ..modules.quiz import generate_quiz, get_quiz, submit_quiz_answer
from .common import _consume_quota_or_raise, _log_progress_activity_safe, services
from ..schemas.request import ArtifactGenerateRequest, QuizGenerateRequest, QuizSubmitRequest, RenameSessionRequest
from ..schemas.response import (
    QuizResponse,
    QuizSubmitResponse,
    SessionListResponse,
)

router = APIRouter(prefix="")


@router.post("/quiz/generate", response_model=QuizResponse)
def api_generate_quiz(request: QuizGenerateRequest, user=Depends(get_current_user)):
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


@router.get("/quiz/sessions", response_model=SessionListResponse)
def list_quiz_sessions_endpoint(
    limit: Optional[int] = Query(None, ge=1, le=100),
    offset: Optional[int] = Query(None, ge=0),
    user=Depends(get_current_user),
):
    page = services.learning.list_quiz_sessions(user["username"], limit=limit, offset=offset)
    return envelope({"sessions": page["items"], "pagination": page["pagination"]}, message_id="MSG-1000")


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


@router.get("/quiz/latest")
def api_get_latest_quiz(session_id: str, user=Depends(get_current_user)):
    quiz = services.learning.get_latest_quiz(user["username"], session_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return envelope({"quiz_id": quiz["quiz_id"], "quiz": quiz["questions"]}, message_id="MSG-1000")


@router.get("/quiz/{quiz_id}")
def api_get_quiz(quiz_id: str, session_id: str, user=Depends(get_current_user)):
    quiz = get_quiz(user["username"], session_id, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return envelope({"quiz_id": quiz["quiz_id"], "quiz": quiz["questions"]}, message_id="MSG-1000")


@router.post("/quiz/{quiz_id}/submit", response_model=QuizSubmitResponse)
def api_submit_quiz(quiz_id: str, request: QuizSubmitRequest, user=Depends(get_current_user)):
    result = submit_quiz_answer(user["username"], request.session_id, quiz_id, request.answers)

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
            return chapter, chapter
    except Exception:
        pass
    return "", ""
