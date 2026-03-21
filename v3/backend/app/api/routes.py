"""
REST APIs
"""

from fastapi import APIRouter
from app.modules.rag import generate_answer
from app.modules.cache import get_cache, set_cache

router = APIRouter()

@router.post("/ask")
def ask(q: dict):
    query = q["query"]

    cached = get_cache(query)
    if cached:
        return {"answer": cached, "cached": True}

    ans = generate_answer(query)
    set_cache(query, ans)

    return {"answer": ans, "cached": False}

@router.post("/admin/reindex")
def full_reindex():
    from app.modules.faiss_store import load_knowledge_base
    load_knowledge_base()
    return {"status": "Reindex started"}


@router.post("/admin/reindex-incremental")
def incremental_reindex():
    from app.modules.faiss_store import load_knowledge_base
    load_knowledge_base()
    return {"status": "Incremental reindex completed"}