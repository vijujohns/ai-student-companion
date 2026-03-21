"""
REST APIs
"""

from fastapi import APIRouter
from fastapi import Depends
from app.modules.rag import generate_answer
from app.modules.cache import get_cache, set_cache
from app.modules.history import get_history
from app.modules.auth import authenticate_user, create_access_token
from app.modules.dependencies import require_role
from app.modules.dependencies import get_current_user
import uuid

router = APIRouter()

#@router.post("/ask")
#def ask(q: dict):
#    query = q["query"]
#
#    cached = get_cache(query)
#    if cached:
#        return {"answer": cached, "cached": True}
#
#    ans = generate_answer(query)
#    set_cache(query, ans)
#
#    return {"answer": ans, "cached": False}


@router.post("/ask")
def ask(q: dict, user=Depends(get_current_user)):
    """
    Protected Ask API
    - Requires JWT token
    - Supports session_id (optional)
    - Uses existing cache logic
    """

    query = q["query"]
    session_id = q.get("session_id")

    # 🔹 Session handling (temporary until frontend manages it)
    if not session_id:
        session_id = str(uuid.uuid4())

    # 🔹 Cache (keep your existing logic)
    cached = get_cache(query)
    if cached:
        return {
            "answer": cached,
            "cached": True,
            "session_id": session_id
        }

    # 🔹 Generate answer
    ans = generate_answer(query)

    # 🔹 Store cache
    set_cache(query, ans)

    return {
        "answer": ans,
        "cached": False,
        "session_id": session_id
    }

#@router.post("/admin/reindex")
#def full_reindex():
#    from app.modules.faiss_store import load_knowledge_base
#    load_knowledge_base()
#    return {"status": "Reindex started"}


@router.post("/admin/reindex")
def reindex(user=Depends(require_role("admin"))):
    from app.modules.faiss_store import load_knowledge_base

    load_knowledge_base()
    return {"status": "Reindex completed"}


@router.post("/admin/reindex-incremental")
#def incremental_reindex():
def incremental_reindex(user=Depends(require_role("admin"))):
    from app.modules.faiss_store import load_knowledge_base
    load_knowledge_base()
    return {"status": "Incremental reindex completed"}

#@router.get("/history")
#def fetch_history(user_id: str, session_id: str):
#    return get_history(user_id, session_id)

@router.get("/history")
def fetch_history(session_id: str, user=Depends(get_current_user)):
    return get_history(user["username"], session_id)


@router.post("/login")
def login(data: dict):
    username = data.get("username")
    password = data.get("password")

    user = authenticate_user(username, password)

    if not user:
        return {"error": "Invalid credentials"}

    token = create_access_token(user)

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"]
    }