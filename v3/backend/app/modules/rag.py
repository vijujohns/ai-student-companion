"""
Improved RAG orchestrator with Redis caching
"""

from app.modules.faiss_store import search
from app.modules.llm import generate_response
from app.modules.cache import get_cache, set_cache
import hashlib
from app.modules.history import save_chat
import os
import uuid


def generate_answer(query: str, user_id="default", session_id=None) -> str:
    """
    RAG pipeline with caching:
    1. Check Redis cache
    2. Retrieve context (FAISS + optional selected content)
    3. Generate answer via LLM
    4. Store in cache
    5. Save chat
    """

    if not session_id:
        session_id = f"{user_id}_default"

    print(f"User ID: {user_id}  Session ID: {session_id}")

    # 🔥 Step 0: Fetch session_content if exists
    from app.modules.db import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT session_content FROM chat_history
        WHERE user_id=? AND session_id=?
        ORDER BY id DESC
        LIMIT 1
    """, (user_id, session_id))
    row = cursor.fetchone()
    session_content_path = row[0] if row else None
    conn.close()

    session_text = ""
    if session_content_path and os.path.exists(session_content_path):
        from app.modules.ingestion import extract_text_from_pdf
        session_text = extract_text_from_pdf(session_content_path)

    # 🔥 Step 1: Create cache key
    key_raw = f"{user_id}:{session_id}:{query}"
    key = hashlib.md5(key_raw.encode()).hexdigest()

    # 🔥 Step 2: Check cache
    cached = get_cache(key)
    if cached:
        print("⚡ Cache HIT")
        return cached["answer"]

    print("❌ Cache MISS")

    # 🔥 Step 3: Retrieve FAISS context
    context_list = search(query)
    context = "\n".join(context_list)

    # Prepend selected PDF/chapter/note content if available
    if session_text:
        context = f"[Selected Content Context]\n{session_text}\n\n{context}"

    # 🔥 Step 4: Add history injection
    from app.modules.history import get_history
    history_data = get_history(user_id, session_id)[-5:]  # limit last 5 messages
    history_text = ""
    for h in history_data:
        history_text += f"user: {h['question']}\n"
        history_text += f"assistant: {h['answer']}\n"

    # 🔥 Step 5: Generate answer via LLM
    answer = generate_response(context, query, history_text)

    # 🔥 Step 6: Store in cache
    set_cache(key, {"answer": answer})

    # 🔥 Step 7: Save chat
    save_chat(user_id, session_id, query, answer)

    return answer