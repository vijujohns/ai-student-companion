"""Compatibility-first utility executor for Step 11 math + translation flows."""

from __future__ import annotations

import re
from typing import Optional

from .math_executor import execute_math_task
from .model_manager import generate_response
from .translation_executor import execute_translation_task

_EXPLORER_REFUSAL = "I'm here to help with learning and educational topics.\nI’m not able to help with that request."
_HARMFUL_EXPLORER_PATTERN = re.compile(
    r"\b(bomb|weapon|gun|knife attack|kill|murder|suicide|self-harm|porn|sexual|nude|rape|abuse|drugs?|meth|cocaine|hack|malware|explosive)\b",
    re.IGNORECASE,
)

_UTILITY_TASKS = {"math", "translation", "explorer"}


def is_utility_task(task: Optional[str]) -> bool:
    return str(task or "").strip().lower() in _UTILITY_TASKS


def _is_harmful_explorer_query(query: str) -> bool:
    return bool(_HARMFUL_EXPLORER_PATTERN.search(str(query or "")))


def execute_explorer_task(
    *,
    query: str,
    user_id: str,
    session_id: str,
    model_name: Optional[str] = None,
    content_id: Optional[str] = None,
) -> str:
    del user_id, session_id, content_id

    if _is_harmful_explorer_query(query):
        return _EXPLORER_REFUSAL

    cleaned_query = str(query or "").strip()
    if not cleaned_query:
        return "Tell me what you want to learn, and I’ll explain it in a simple, student-friendly way."

    context = (
        "You are Brain Teaser in Explorer Mode for students. "
        "Give safe, age-appropriate, educational answers using general knowledge only. "
        "Do not claim to use uploaded files or hidden context. "
        "If a request is unsafe or inappropriate, refuse briefly and redirect to learning help."
    )
    response = generate_response(context, cleaned_query, model_name=model_name, task="qa")
    return str(response or "").strip() or "Tell me what you want to learn, and I’ll explain it in a simple, student-friendly way."


def execute_utility_task(
    *,
    task: str,
    query: str,
    user_id: str,
    session_id: str,
    model_name: Optional[str] = None,
    content_id: Optional[str] = None,
) -> str:
    normalized = str(task or "").strip().lower()
    if normalized == "math":
        return execute_math_task(
            query=query,
            user_id=user_id,
            session_id=session_id,
            model_name=model_name,
            content_id=content_id,
        )
    if normalized == "translation":
        return execute_translation_task(
            query=query,
            user_id=user_id,
            session_id=session_id,
            model_name=model_name,
            content_id=content_id,
        )
    if normalized == "explorer":
        return execute_explorer_task(
            query=query,
            user_id=user_id,
            session_id=session_id,
            model_name=model_name,
            content_id=content_id,
        )
    raise ValueError(f"Unsupported utility task: {task}")
