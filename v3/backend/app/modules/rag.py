"""
RAG (Retrieval-Augmented Generation) orchestrator
- Redis caching
- Dynamic model selection (local/cloud)
- Streaming support
- Enhanced fallback handling
"""

import hashlib
import os
import time
from typing import List

from .cache import get_cache, set_cache
from .db import get_connection
from .faiss_store import documents, search
from .file_management import resolve_content_reference
from .history import get_history, save_chat
from .model_manager import generate_response, generate_response_stream
from ..core.config_loader import get_rag_top_k
from ..core.debug_logger import dlog


# -------------------------
# Utility Functions
# -------------------------
def rank_chunks(query: str, chunks: List[str]) -> List[str]:
    query_words = set(query.lower().split())
    scored = [(len(query_words.intersection(set(c.lower().split()))), c) for c in chunks]
    scored.sort(reverse=True, key=lambda x: x[0])
    return [c for _, c in scored]


def is_context_relevant(query: str, context: str) -> bool:
    return len(set(query.lower().split()).intersection(set(context.lower().split()))) > 2


def clean_output(text: str) -> str:
    """Remove unwanted patterns, duplicate lines, and repeated words."""
    stop_markers = ["Question:", "Answer:", "User:", "assistant:", "Q:", "A:"]
    for marker in stop_markers:
        if marker in text:
            text = text.split(marker)[0]

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    unique_lines = []
    for line in lines:
        if line not in unique_lines:
            unique_lines.append(line)
    text = " ".join(unique_lines)

    words = text.split()
    cleaned_words = [w for i, w in enumerate(words) if i == 0 or w != words[i - 1]]
    return " ".join(cleaned_words).strip()


def _build_cache_key(user_id: str, session_id: str, query: str, model_name: str, session_content_ref: str) -> str:
    raw = f"{user_id}:{session_id}:{query}:{model_name}:{session_content_ref}"
    return hashlib.sha256(raw.encode()).hexdigest()


# -------------------------
# Core RAG Functions
# -------------------------
def generate_answer(
    query: str,
    user_id: str = "default",
    session_id: str = None,
    model_name: str = None,
) -> str:
    """Generate answer (non-streaming) with caching, history, and fallback."""
    t_start = time.perf_counter()
    if not session_id:
        session_id = f"{user_id}_default"

    dlog(
        "RAG",
        "generate_answer called",
        user=user_id,
        session=session_id,
        query=query[:120],
        requested_model=model_name or "auto",
    )

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_content FROM chat_history
        WHERE user_id=? AND session_id=?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id, session_id),
    )
    row = cursor.fetchone()
    session_content_ref = row[0] if row else None
    conn.close()

    resolved_content = None
    if session_content_ref:
        try:
            resolved_content = resolve_content_reference({"username": user_id}, session_content_ref)
        except Exception:
            resolved_content = None

    session_content_path = resolved_content["path"] if resolved_content else None
    cache_content_ref = resolved_content["content_id"] if resolved_content else session_content_ref

    key = _build_cache_key(user_id, session_id, query, model_name, cache_content_ref)
    cached = get_cache(key)
    if cached:
        elapsed = (time.perf_counter() - t_start) * 1000
        dlog("RAG", "Cache HIT", elapsed_ms=f"{elapsed:.1f}ms")
        return cached["answer"]

    history_data = get_history(user_id, session_id)[-3:]
    last_question = history_data[-1]["question"] if history_data else ""
    enhanced_query = f"{query}. Context: {last_question}" if last_question and len(query) < 80 else query

    top_k = get_rag_top_k(default=4)
    context_list = search(
        enhanced_query,
        filter_path=session_content_path,
        top_k=top_k,
        search_k=max(8, top_k * 2),
    )
    context_list = rank_chunks(enhanced_query, context_list)[:top_k]

    raw_context = "\n".join(context_list)
    context = raw_context if is_context_relevant(query, raw_context) else ""

    history_text = "".join(
        [f"user: {h['question']}\nassistant: {h['answer']}\n" for h in history_data]
    )

    answer = generate_response(context=context, query=query, history=history_text, model_name=model_name)

    fallback_used = False
    if any(x in answer.lower() for x in ["could not find", "not found in the context", "not in the provided"]):
        fallback_used = True
        fallback_prompt = f"""
You are a helpful AI tutor.
Answer the question clearly using your general knowledge.
Keep it simple and student-friendly.
Question: {query}
Answer:
"""
        answer = generate_response("", fallback_prompt, "", model_name)
        answer = "This answer is based on my general knowledge, not from your study material.\n\n" + answer

    answer = clean_output(answer)
    set_cache(key, {"answer": answer})
    save_chat(user_id, session_id, query, answer)

    total_elapsed = (time.perf_counter() - t_start) * 1000
    dlog(
        "RAG",
        "generate_answer complete",
        elapsed_ms=f"{total_elapsed:.1f}ms",
        fallback_used=fallback_used,
        answer_chars=len(answer),
    )
    return answer


def generate_answer_stream(query, user_id="default", session_id=None, model_name=None):
    """Stream answer token-by-token (generator) with caching and fallback."""
    t_start = time.perf_counter()
    if not session_id:
        session_id = f"{user_id}_default"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_content FROM chat_history
        WHERE user_id=? AND session_id=?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id, session_id),
    )
    row = cursor.fetchone()
    session_content_ref = row[0] if row else None
    conn.close()

    resolved_content = None
    if session_content_ref:
        try:
            resolved_content = resolve_content_reference({"username": user_id}, session_content_ref)
        except Exception:
            resolved_content = None

    session_content_path = resolved_content["path"] if resolved_content else None
    cache_content_ref = resolved_content["content_id"] if resolved_content else session_content_ref

    key = _build_cache_key(user_id, session_id, query, model_name, cache_content_ref)
    cached = get_cache(key)
    if cached:
        for token in cached["answer"].split():
            yield token + " "
        return

    history_data = get_history(user_id, session_id)[-3:]
    last_question = history_data[-1]["question"] if history_data else ""
    enhanced_query = f"{query}. Context: {last_question}" if last_question and len(query) < 80 else query

    top_k = get_rag_top_k(default=4)
    context_list = search(
        enhanced_query,
        filter_path=session_content_path,
        top_k=top_k,
        search_k=max(8, top_k * 2),
    )
    context_list = rank_chunks(enhanced_query, context_list)[:top_k]
    context = "\n".join(context_list)

    history_text = "".join(
        [f"user: {h['question']}\nassistant: {h['answer']}\n" for h in history_data]
    )

    full_response = ""
    for token in generate_response_stream(context, query, history_text, model_name):
        yield token
        full_response += token

    if any(x in full_response.lower() for x in ["could not find", "not found in the context", "not in the provided"]):
        fallback_prompt = f"""
You are a helpful AI tutor.
Answer the question clearly using your general knowledge.
Keep it simple and student-friendly.
Question: {query}
Answer:
"""
        yield "This answer is based on my general knowledge, not from your study material.\n\n"
        full_response = ""
        for token in generate_response_stream("", fallback_prompt, "", model_name):
            full_response += token
            yield token

    full_response = clean_output(full_response)
    set_cache(key, {"answer": full_response})
    save_chat(user_id, session_id, query, full_response)

    elapsed = (time.perf_counter() - t_start) * 1000
    dlog("RAG", "generate_answer_stream complete", elapsed_ms=f"{elapsed:.1f}ms")


# -------------------------
# Retrieve knowledge chunks (lesson/quiz context)
# -------------------------
def retrieve_chunks(chapter: str, top_k: int = 5):
    """
    Retrieve chapter-relevant chunks from the indexed documents.

    Strategy:
    1. Prefer chunks whose source path contains chapter keywords.
    2. Fall back to FAISS semantic search.
    """
    query = (chapter or "").strip()
    if not query:
        return []

    chapter_terms = {w for w in query.lower().replace("-", " ").split() if len(w) > 1}

    source_matches = []
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        source = (doc.get("source") or "").lower()
        text = doc.get("text", "")
        if not source or not text:
            continue

        source_words = set(source.replace("\\", " ").replace("/", " ").replace("-", " ").split())
        overlap = len(chapter_terms.intersection(source_words))
        if overlap > 0:
            source_matches.append((overlap, text))

    if source_matches:
        source_matches.sort(reverse=True, key=lambda x: x[0])
        return [text for _, text in source_matches[:top_k]]

    return search(query, top_k=top_k, search_k=max(8, top_k * 2))
