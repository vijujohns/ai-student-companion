"""
Improved RAG orchestrator with Redis caching
"""

from app.modules.faiss_store import search
from app.modules.llm import generate_response
from app.modules.cache import get_cache, set_cache
import hashlib
from app.modules.history import save_chat
import uuid


def generate_answer(query: str, user_id="default", session_id=None) -> str:
    """
    RAG pipeline with caching:
    1. Check Redis cache
    2. Retrieve context
    3. Generate answer via LLM
    4. Store in cache
    """

    if not session_id:
        session_id = f"{user['username']}_default"

    print(f"User ID: {user_id}  Session ID: {session_id}")

    # 🔥 Step 1: Create cache key
    key_raw = f"{user_id}:{session_id}:{query}"
    key = hashlib.md5(key_raw.encode()).hexdigest()

    # 🔥 Step 2: Check cache
    cached = get_cache(key)
    if cached:
        print("⚡ Cache HIT")
        return cached["answer"]
    else:
        print("❌ Cache MISS")

        # Step 3: Retrieve context
        context_list = search(query)
        context = "\n".join(context_list)

        # Step 4 : Add history injection
        from app.modules.history import get_history

        history_data = get_history(user_id, session_id)
        history_data = history_data[-5:]  # limit

        history_text = ""
        for h in history_data:
            history_text += f"user: {h['question']}\n"
            history_text += f"assistant: {h['answer']}\n"

        # Step 5: Generate answer
        answer = generate_response(context, query, history_text)
        
        # Step 6: Store in cache
        set_cache(key, {"answer": answer})

    # 🔥 Save chat
    save_chat(user_id, session_id, query, answer)

    return answer