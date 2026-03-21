"""
Improved RAG orchestrator with Redis caching
"""

from app.modules.faiss_store import search
from app.modules.llm import generate_response
from app.modules.cache import get_cache, set_cache
import hashlib


def generate_answer(query: str) -> str:
    """
    RAG pipeline with caching:
    1. Check Redis cache
    2. Retrieve context
    3. Generate answer via LLM
    4. Store in cache
    """

    # 🔥 Step 1: Create cache key
    key = hashlib.md5(query.encode()).hexdigest()

    # 🔥 Step 2: Check cache
    cached = get_cache(key)
    if cached:
        print("⚡ Cache HIT")
        return cached["answer"]

    print("❌ Cache MISS")

    # Step 3: Retrieve context
    context_list = search(query)
    context = "\n".join(context_list)

    # Step 4: Generate answer
    answer = generate_response(context, query)

    # Step 5: Store in cache
    set_cache(key, {"answer": answer})

    return answer