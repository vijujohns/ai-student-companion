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

    if not session_id:
        session_id = str(uuid.uuid4())

    cached = get_cache(query)
    if cached:
        return {
            "answer": cached,
            "cached": True,
            "session_id": session_id
        }

    ans = generate_answer(
        query,
        user_id=user["username"],
        session_id=session_id
    )

    set_cache(query, ans)

    return {
        "answer": ans,
        "cached": False,
        "session_id": session_id
    }


@router.post("/admin/reindex")
def reindex(user=Depends(require_role("admin"))):
    from app.modules.faiss_store import load_knowledge_base

    load_knowledge_base()
    return {"status": "Reindex completed"}


@router.post("/admin/reindex-incremental")
def incremental_reindex(user=Depends(require_role("admin"))):
    from app.modules.faiss_store import load_knowledge_base
    load_knowledge_base()
    return {"status": "Incremental reindex completed"}


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


# ✅ UPDATED: Use session_title from DB
@router.get("/sessions")
def get_sessions(user=Depends(get_current_user)):
    """
    Return sessions with persisted titles
    """
    from app.modules.db import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT 
        session_id,
        MAX(session_title),
        MAX(timestamp)
    FROM chat_history
    WHERE user_id=?
    GROUP BY session_id
    ORDER BY MAX(timestamp) DESC
    """, (user["username"],))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "title": r[1] if r[1] else "New Chat",
            "last_updated": r[2]
        }
        for r in rows
    ]


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, user=Depends(get_current_user)):
    from app.modules.db import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM chat_history
    WHERE user_id=? AND session_id=?
    """, (user["username"], session_id))

    conn.commit()
    conn.close()

    return {"status": "deleted"}


# ✅ NEW: Persist rename
@router.put("/sessions/{session_id}")
def rename_session(session_id: str, data: dict, user=Depends(get_current_user)):
    new_title = data.get("title")

    if not new_title:
        return {"error": "Title required"}

    from app.modules.db import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE chat_history
    SET session_title=?
    WHERE user_id=? AND session_id=?
    """, (new_title, user["username"], session_id))

    conn.commit()
    conn.close()

    return {"status": "updated"}
