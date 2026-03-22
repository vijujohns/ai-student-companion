"""
REST APIs
"""

from fastapi import APIRouter, Depends
from app.modules.rag import generate_answer
from app.modules.cache import get_cache, set_cache
from app.modules.history import get_history
from app.modules.auth import authenticate_user, create_access_token
from app.modules.dependencies import require_role, get_current_user
import uuid
from fastapi.responses import FileResponse
from urllib.parse import unquote
import os
from app.modules.flashcards import router as flashcards_router

router = APIRouter()

router.include_router(flashcards_router)

@router.post("/ask")
def ask(q: dict, user=Depends(get_current_user)):
    """
    Protected Ask API
    - Requires JWT token
    - Supports session_id (optional)
    - Supports model selection via 'model_name' (optional)
    - Uses Redis cache for faster responses
    """

    query = q["query"]
    session_id = q.get("session_id")
    model_name = q.get("model_name")  # NEW: Optional model selection

    if not session_id:
        session_id = str(uuid.uuid4())

    # 🔹 Generate answer via RAG pipeline (handles caching internally)
    ans = generate_answer(
        query=query,
        user_id=user["username"],
        session_id=session_id,
        model_name=model_name  # Pass optional model selection
    )

    return {
        "answer": ans,
        "cached": False,  # generate_answer internally handles cache hits
        "session_id": session_id,
        "model_used": model_name if model_name else "default"
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


@router.put("/sessions/{session_id}")
def rename_session(session_id: str, data: dict, user=Depends(get_current_user)):
    """
    Persistently rename a session
    """
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


@router.get("/sessions/{session_id}/content")
def get_session_content(session_id: str, user=Depends(get_current_user)):
    from app.modules.db import get_connection
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
    return {"session_content": row[0] if row else None}


@router.put("/sessions/{session_id}/content")
def set_session_content(session_id: str, data: dict, user=Depends(get_current_user)):
    """
    Update session content path (PDF etc.)
    """
    path = data.get("path")
    if not path:
        return {"error": "Content path required"}

    from app.modules.db import get_connection
    conn = get_connection()
    cursor = conn.cursor()

    # Update all future chats for this session with new content
    cursor.execute("""
        UPDATE chat_history
        SET session_content=?
        WHERE user_id=? AND session_id=? AND session_content IS NULL
    """, (path, user["username"], session_id))

    conn.commit()
    conn.close()
    return {"status": "updated", "session_content": path}


@router.get("/pdf")
def serve_pdf(path: str, user=Depends(get_current_user)):
    """
    Serve PDF from knowledge base folder safely
    """
    path = unquote(path)  # decode URL-encoded path

    # Security check: only serve from knowledge base
    BASE_KB = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")), "knowledge_base")
    full_path = os.path.abspath(path)

    if not full_path.startswith(BASE_KB) or not os.path.exists(full_path):
        return {"error": "File not found or access denied"}

    return FileResponse(full_path, media_type="application/pdf")


# 🔹 Knowledge Base Endpoints
@router.get("/classes")
def get_classes():
    """
    Return available classes
    """
    KB_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")), "knowledge_base")
    if not os.path.exists(KB_DIR):
        return []
    return sorted([d for d in os.listdir(KB_DIR) if os.path.isdir(os.path.join(KB_DIR, d))])


@router.get("/subjects")
def get_subjects(class_name: str):
    """
    Return subjects for a given class
    """
    KB_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")), "knowledge_base")
    class_path = os.path.join(KB_DIR, class_name)
    if not os.path.exists(class_path):
        return []
    return sorted([d for d in os.listdir(class_path) if os.path.isdir(os.path.join(class_path, d))])


@router.get("/folders")
def get_folders(class_name: str, subject: str):
    """
    Return folders for a given class and subject
    """
    KB_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")), "knowledge_base")
    subject_path = os.path.join(KB_DIR, class_name, subject)
    if not os.path.exists(subject_path):
        return []
    return sorted([d for d in os.listdir(subject_path) if os.path.isdir(os.path.join(subject_path, d))])


@router.get("/contents")
def get_contents(class_name: str, subject: str, folder: str):
    """
    Return contents (PDFs etc.) for a given class, subject, and folder
    """
    KB_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")), "knowledge_base")
    folder_path = os.path.join(KB_DIR, class_name, subject, folder)
    if not os.path.exists(folder_path):
        return []

    contents = []
    for f in os.listdir(folder_path):
        full_path = os.path.join(folder_path, f)
        if os.path.isfile(full_path) and f.lower().endswith(".pdf"):
            contents.append({"title": os.path.splitext(f)[0], "path": full_path})
    return contents