"""Compatibility-first utility executor for Step 11 math + translation flows."""

from __future__ import annotations

from typing import Optional

from .math_executor import execute_math_task
from .translation_executor import execute_translation_task

_UTILITY_TASKS = {"math", "translation"}


def is_utility_task(task: Optional[str]) -> bool:
    return str(task or "").strip().lower() in _UTILITY_TASKS


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
    raise ValueError(f"Unsupported utility task: {task}")
