from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..modules.dependencies import get_current_user
from ..modules.lesson_plan import (
    complete_lesson_card,
    generate_lesson_plan,
    get_lesson_plan,
    get_lesson_plan_cards,
    get_next_step,
    update_step_progress,
)
from ..modules.messages import envelope
from .common import _consume_quota_or_raise, _log_progress_activity_safe, services
from ..schemas.request import LessonPlanCreateRequest, LessonProgressRequest, RenameSessionRequest
from ..schemas.response import (
    LessonPlanResponse,
    LessonPlanResponseEnvelope,
    SessionListResponseEnvelope,
)

router = APIRouter(prefix="/lesson-plan")


@router.post("/create", response_model=LessonPlanResponseEnvelope)
def create_plan(request: LessonPlanCreateRequest, user=Depends(get_current_user)):
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
        raise

    _log_progress_activity_safe(
        user,
        "lesson",
        subject=request.chapter,
        chapter=request.chapter,
        duration_seconds=60,
    )
    return envelope(plan, message_id="MSG-1000")


@router.get("/sessions", response_model=SessionListResponseEnvelope)
def get_lesson_sessions(
    limit: Optional[int] = Query(None, ge=1, le=100),
    offset: Optional[int] = Query(None, ge=0),
    user=Depends(get_current_user),
):
    page = services.learning.list_lesson_sessions(user["username"], limit=limit, offset=offset)
    return envelope({"sessions": page["items"], "pagination": page["pagination"]}, message_id="MSG-1000")


@router.put("/sessions/{session_id}")
def rename_lesson_plan_session(session_id: str, request: RenameSessionRequest, user=Depends(get_current_user)):
    result = services.learning.rename_lesson_session(user["username"], session_id, request.title)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Lesson session not found")
    return envelope(result, message_id="MSG-1000")


@router.delete("/sessions/{session_id}")
def remove_lesson_plan_session(session_id: str, user=Depends(get_current_user)):
    result = services.learning.delete_lesson_session(user["username"], session_id)
    return envelope(result, message_id="MSG-1000")


@router.get("", response_model=LessonPlanResponseEnvelope)
def fetch_plan(session_id: str, user=Depends(get_current_user)):
    plan = get_lesson_plan(user["username"], session_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Lesson plan not found")
    return envelope(plan, message_id="MSG-1000")


@router.post("/progress")
def update_progress(request: LessonProgressRequest, user=Depends(get_current_user)):
    result = update_step_progress(
        user["username"],
        request.session_id,
        request.step_id,
        request.status,
    )
    return envelope(result, message_id="MSG-1000")


@router.get("/next")
def next_step(session_id: str, user=Depends(get_current_user)):
    nxt = get_next_step(user["username"], session_id)
    return envelope({"next_step": nxt}, message_id="MSG-1000")


@router.get("/{lesson_plan_id}/cards")
def lesson_cards(lesson_plan_id: int, user=Depends(get_current_user)):
    cards = get_lesson_plan_cards(user["username"], lesson_plan_id)
    if not cards:
        raise HTTPException(status_code=404, detail="Lesson cards not found")
    return envelope({"lesson_plan_id": lesson_plan_id, "cards": cards}, message_id="MSG-1000")


@router.post("/{lesson_plan_id}/cards/{card_id}/complete")
def complete_card(lesson_plan_id: int, card_id: int, user=Depends(get_current_user)):
    result = complete_lesson_card(user["username"], lesson_plan_id, card_id, status="completed")
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Lesson card not found")

    _log_progress_activity_safe(user, "lesson", duration_seconds=300)
    return envelope(result, message_id="MSG-1000")
