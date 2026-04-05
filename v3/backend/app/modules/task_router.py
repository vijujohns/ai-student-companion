"""Lightweight task-routing for compatibility-first orchestration.

Step 7 introduces an additive router shell behind the existing `/ask` and
`/ws/ask` flows. The router currently classifies intent and chooses the most
appropriate existing model task without changing public API contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

from ..core.debug_logger import dlog


_SUPPORTED_TASKS = {
    "qa",
    "summary",
    "lesson",
    "quiz",
    "flashcards",
    "assessment",
    "translation",
    "math",
    "explorer",
    "admin/system",
}

_TASK_ALIASES = {
    "ask": "qa",
    "chat": "qa",
    "question_answer": "qa",
    "question-answer": "qa",
    "summarise": "summary",
    "summarize": "summary",
    "lesson_plan": "lesson",
    "lesson-plan": "lesson",
    "learn": "lesson",
    "study": "lesson",
    "mcq": "quiz",
    "test": "quiz",
    "exam": "assessment",
    "flashcard": "flashcards",
    "cards": "flashcards",
    "translate": "translation",
    "explore": "explorer",
    "general": "explorer",
    "general_chat": "explorer",
    "explorer_mode": "explorer",
}

_SUMMARY_HINTS = (
    "summarize",
    "summarise",
    "summary",
    "overview",
    "key points",
    "main points",
    "short note",
)
_FLASHCARD_HINTS = ("flashcard", "flash card", "revision card", "study cards")
_QUIZ_HINTS = ("quiz", "mcq", "multiple choice", "practice test", "quick test")
_ASSESSMENT_HINTS = ("assessment", "exam paper", "question paper", "mock test")
_LESSON_HINTS = ("teach me", "lesson", "study plan", "walk me through", "explain this chapter")
_TRANSLATION_HINTS = ("translate", "translation", "in hindi", "in tamil", "in french", "in spanish")
_MATH_PATTERN = re.compile(
    r"(solve\s+for|what\s+is\s+\d+\s*[+\-*/^=]|\d+\s*[+\-*/^=]\s*\d+|equation|algebra|geometry|integrate|differentiate|derivative|fraction|calculate|refractive\s+index|speed\s+of\s+light)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TaskRoute:
    task: str
    model_task: str
    retrieval_scope: str
    confidence: float
    reason: str
    source: str
    explicit: bool = False


def normalize_task_name(task: Optional[str]) -> Optional[str]:
    raw = str(task or "").strip().lower()
    if not raw:
        return None

    normalized = raw.replace("-", "_").replace(" ", "_")
    alias = _TASK_ALIASES.get(normalized, normalized)
    return alias if alias in _SUPPORTED_TASKS else None


def _model_task_for(task: str) -> str:
    if task in {"qa", "summary", "lesson", "quiz", "flashcards", "explorer", "math", "translation"}:
        return task
    return "qa"


def _scope_for(task: str, content_id: Optional[str]) -> str:
    if task == "explorer":
        return "general"
    if content_id:
        return "selected_content"
    if task in {"lesson", "quiz", "assessment", "flashcards", "summary"}:
        return "curriculum"
    return "general"


def _build_route(task: str, route: str, confidence: float, reason: str, *, content_id: Optional[str], explicit: bool = False) -> TaskRoute:
    return TaskRoute(
        task=task,
        model_task=_model_task_for(task),
        retrieval_scope=_scope_for(task, content_id),
        confidence=round(float(confidence), 2),
        reason=reason,
        source=route,
        explicit=explicit,
    )


def route_task(
    query: str,
    *,
    route: str = "/ask",
    requested_task: Optional[str] = None,
    model_name: Optional[str] = None,
    content_id: Optional[str] = None,
) -> TaskRoute:
    """Return a lightweight routing decision for the current request.

    The router is intentionally heuristic and compatibility-first. It does not
    replace the existing specialized lesson/quiz/flashcard endpoints; it only
    helps `/ask` and `/ws/ask` choose the best existing task/model path.
    """

    explicit_task = normalize_task_name(requested_task)
    if explicit_task:
        decision = _build_route(
            explicit_task,
            route,
            0.99,
            f"explicit:{explicit_task}",
            content_id=content_id,
            explicit=True,
        )
        dlog("ROUTER", "Task routed", task=decision.task, source=decision.source, reason=decision.reason, confidence=decision.confidence, requested_model=model_name or "auto")
        return decision

    route_key = str(route or "").strip().lower()
    if "lesson" in route_key:
        decision = _build_route("lesson", route_key, 0.98, "route:lesson", content_id=content_id)
    elif "quiz" in route_key:
        decision = _build_route("quiz", route_key, 0.98, "route:quiz", content_id=content_id)
    elif "flashcard" in route_key:
        decision = _build_route("flashcards", route_key, 0.98, "route:flashcards", content_id=content_id)
    else:
        text = str(query or "").strip().lower()
        if any(term in text for term in _SUMMARY_HINTS):
            decision = _build_route("summary", route_key, 0.9 if content_id else 0.78, "summary:keywords", content_id=content_id)
        elif any(term in text for term in _FLASHCARD_HINTS):
            decision = _build_route("flashcards", route_key, 0.88, "keyword:flashcards", content_id=content_id)
        elif any(term in text for term in _QUIZ_HINTS):
            decision = _build_route("quiz", route_key, 0.86, "keyword:quiz", content_id=content_id)
        elif any(term in text for term in _ASSESSMENT_HINTS):
            decision = _build_route("assessment", route_key, 0.85, "keyword:assessment", content_id=content_id)
        elif any(term in text for term in _TRANSLATION_HINTS):
            decision = _build_route("translation", route_key, 0.84, "keyword:translation", content_id=content_id)
        elif any(term in text for term in _LESSON_HINTS):
            decision = _build_route("lesson", route_key, 0.8, "keyword:lesson", content_id=content_id)
        elif _MATH_PATTERN.search(text):
            decision = _build_route("math", route_key, 0.74, "pattern:math", content_id=content_id)
        else:
            decision = _build_route("qa", route_key or "/ask", 0.55, "fallback:qa", content_id=content_id)

    dlog(
        "ROUTER",
        "Task routed",
        task=decision.task,
        model_task=decision.model_task,
        source=decision.source,
        reason=decision.reason,
        confidence=decision.confidence,
        requested_model=model_name or "auto",
    )
    return decision
