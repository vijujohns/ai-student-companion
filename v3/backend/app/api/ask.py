"""
Ask and generator routing module.
"""
import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from ..modules.rag import generate_answer
from ..modules.dependencies import get_current_user
from ..modules.messages import envelope, get_message
from ..modules.policy import consume_quota, release_usage
from ..modules.task_router import route_task
from ..modules.generator_executor import execute_generator_task, is_generator_task
from ..modules.utility_executor import execute_utility_task, is_utility_task
from ..schemas.request import AskRequest

router = APIRouter()


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


@router.post("/ask")
def ask(request: AskRequest, user=Depends(get_current_user)):
    query = request.query
    session_id = request.session_id
    model_name = request.model_name

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
        "model_used": model_name if model_name else "default",
    }, message_id="MSG-1000")
