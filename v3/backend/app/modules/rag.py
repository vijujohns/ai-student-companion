"""
RAG (Retrieval-Augmented Generation) orchestrator with Redis caching
and dynamic model selection.

This module handles the full RAG pipeline:
1. Fetch session-specific selected content (PDFs / notes)
2. Check Redis cache for repeated queries
3. Retrieve FAISS context relevant to the query
4. Generate answer using the selected LLM (local or cloud)
5. Store answer in cache
6. Persist chat history

Enhancement:
- Supports selecting a specific model dynamically via `model_name`
  using the unified Model Manager (local or cloud LLMs)
"""

import os
import uuid
import hashlib
from app.modules.faiss_store import search
from app.modules.cache import get_cache, set_cache
from app.modules.history import save_chat, get_history
from app.modules.db import get_connection

# 🔹 Unified LLM interface (local + cloud)
from app.modules.model_manager import generate_response


def generate_answer(
    query: str,
    user_id: str = "default",
    session_id: str = None,
    model_name: str = None
) -> str:
    """
    Main RAG function to generate answers with caching and optional model selection.

    Parameters:
    - query: User's question
    - user_id: Unique identifier for the user
    - session_id: Optional session identifier; auto-generated if missing
    - model_name: Optional model name to use (local or cloud)

    Returns:
    - answer: Generated response string
    """

    # Step 0: Ensure session ID exists
    if not session_id:
        session_id = f"{user_id}_default"

    print(f"User ID: {user_id}  Session ID: {session_id}")

    # Step 1: Fetch any session-specific content (PDFs, notes, etc.)
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

    #session_text = ""
    #if session_content_path and os.path.exists(session_content_path):
    #    from app.modules.ingestion import extract_text_from_pdf
    #    session_text = extract_text_from_pdf(session_content_path)

    # Step 2: Generate a cache key including model name
    key_raw = f"{user_id}:{session_id}:{query}:{model_name}:{session_content_path}"
    key = hashlib.md5(key_raw.encode()).hexdigest()

    # Step 3: Check Redis cache
    cached = get_cache(key)
    if cached:
        print("⚡ Cache HIT")
        return cached["answer"]

    print("❌ Cache MISS")

    # Step 4: Retrieve FAISS context relevant to the query
    context_list = search(query, filter_path=session_content_path)
    context = "\n".join(context_list)

    # Include session-specific content at the top of context if available
    #if session_text:
    #    context = f"[Selected Content Context]\n{session_text}\n\n{context}"

    # Step 5: Inject last 5 messages from session history
    history_data = get_history(user_id, session_id)[-3:]  # last 3 exchanges
    history_text = ""
    for h in history_data:
        history_text += f"user: {h['question']}\n"
        history_text += f"assistant: {h['answer']}\n"

    # Step 6: Generate answer using selected model (local or cloud)
    # If model_name is None, default model is used (tinyllama-1.1b-chat)
    answer = generate_response(
        context=context,
        query=query,
        history=history_text,
        model_name=model_name
    )

    # Step 7: Store generated answer in Redis cache
    set_cache(key, {"answer": answer})

    # Step 8: Persist chat history
    #save_chat(user_id, session_id, query, answer)

    return answer


def generate_answer_stream(query, user_id="default", session_id=None, model_name=None):

    if not session_id:
        session_id = f"{user_id}_default"

    # 🔹 Get session content path
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT session_content FROM chat_history
        WHERE user_id=? AND session_id=?
        ORDER BY id DESC LIMIT 1
    """, (user_id, session_id))
    row = cursor.fetchone()
    session_content_path = row[0] if row else None
    conn.close()



    import hashlib
    from app.modules.cache import get_cache, set_cache

    key_raw = f"{user_id}:{session_id}:{query}:{model_name}:{session_content_path}"
    key = hashlib.md5(key_raw.encode()).hexdigest()

    cached = get_cache(key)
    if cached:
        print("⚡ STREAM CACHE HIT")
        yield cached["answer"]
        return

    # 🔹 Retrieve context (filtered)
    context_list = search(query, filter_path=session_content_path)
    context = "\n".join(context_list)

    # 🔹 History
    history_data = get_history(user_id, session_id)[-3:]
    history_text = ""
    for h in history_data:
        history_text += f"user: {h['question']}\nassistant: {h['answer']}\n"

    # 🔹 STREAM FROM MODEL
    from app.modules.model_manager import generate_response_stream

    full_response = ""

    for token in generate_response_stream(context, query, history_text, model_name):
        full_response += token
        yield token