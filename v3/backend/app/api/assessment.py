from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..modules.assessment import (
    generate_question_paper,
    generate_subject_quiz,
    get_assessment_paper,
    list_assessment_papers,
    record_assessment_attempt,
)
from ..modules.dependencies import get_current_user
from ..modules.messages import envelope
from .common import _consume_quota_or_raise, _log_progress_activity_safe
from ..schemas.request import AssessmentAttemptRequest, QuestionPaperRequest, SubjectQuizRequest
from ..schemas.response import (
    QuizResponse,
)

router = APIRouter(prefix="/assessment")


@router.post("/subject-quiz", response_model=QuizResponse)
def api_generate_subject_quiz(request: SubjectQuizRequest, user=Depends(get_current_user)):
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
        raise

    _log_progress_activity_safe(
        user,
        "assessment",
        subject=request.subject,
        chapter=request.subject,
        duration_seconds=120,
    )
    return envelope(result, message_id="MSG-1000")


@router.post("/question-paper", response_model=QuizResponse)
def api_generate_question_paper(request: QuestionPaperRequest, user=Depends(get_current_user)):
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
        raise

    _log_progress_activity_safe(
        user,
        "assessment",
        subject=request.subject,
        chapter=request.subject,
        duration_seconds=120,
    )
    return envelope(result, message_id="MSG-1000")


@router.get("/papers")
def api_list_assessment_papers(
    paper_type: Optional[str] = None,
    user=Depends(get_current_user),
):
    papers = list_assessment_papers(user["username"], paper_type=paper_type)
    return envelope({"papers": papers}, message_id="MSG-1000")


@router.get("/papers/{paper_id}")
def api_get_assessment_paper(paper_id: int, user=Depends(get_current_user)):
    paper = get_assessment_paper(user["username"], paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Assessment paper not found")
    return envelope({"paper": paper}, message_id="MSG-1000")


@router.post("/papers/{paper_id}/attempt")
def api_record_assessment_attempt(
    paper_id: int,
    request: AssessmentAttemptRequest,
    user=Depends(get_current_user),
):
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
