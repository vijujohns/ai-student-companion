"""
RAG (Retrieval-Augmented Generation) orchestrator
- Redis caching
- Dynamic model selection (local/cloud)
- Streaming support
- Enhanced fallback handling
"""

import hashlib
import os
import re
import time
from typing import Any, List

from .cache import get_cache, set_cache
from .db import get_connection
from .faiss_store import documents, search
from .file_management import resolve_content_reference
from .history import get_history, save_chat
from .ingestion import get_summary
from .model_manager import generate_response, generate_response_stream
from ..core.config_loader import get_rag_top_k
from ..core.debug_logger import dlog


_CONTENT_UNSET = object()
_GROUNDING_FALLBACK = "I don't have enough information in the provided material."
_GROUNDING_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "what", "which", "who", "when", "where",
    "why", "how", "this", "that", "these", "those", "and", "or", "but", "for", "with", "from",
    "into", "about", "your", "their", "them", "then", "than", "have", "has", "had", "does", "did",
    "not", "can", "could", "would", "should", "using", "used", "only", "based", "provided", "material",
    "study", "chunk", "answer",
}
_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")


# -------------------------
# Utility Functions
# -------------------------
def _grounding_terms(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(str(text or "").lower())
        if len(token) > 2 and token not in _GROUNDING_STOPWORDS
    }


def rank_chunks(query: str, chunks: List[str]) -> List[str]:
    query_words = set(query.lower().split())
    scored = [(len(query_words.intersection(set(c.lower().split()))), c) for c in chunks]
    scored.sort(reverse=True, key=lambda x: x[0])
    return [c for _, c in scored]


def is_context_relevant(query: str, context: str) -> bool:
    query_terms = _grounding_terms(query)
    context_terms = _grounding_terms(context)
    if not query_terms or not context_terms:
        return False
    overlap = query_terms.intersection(context_terms)
    return bool(overlap)


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


def _normalize_retrieval_item(item: Any) -> dict:
    if isinstance(item, dict):
        return {
            "text": str(item.get("text") or "").strip(),
            "source": item.get("source"),
            "metadata": dict(item.get("metadata") or {}),
            "score": float(item.get("score", 0.0) or 0.0),
            "index_name": str(item.get("index_name") or (item.get("metadata") or {}).get("index_name") or "general_index"),
        }
    return {
        "text": str(item or "").strip(),
        "source": None,
        "metadata": {},
        "score": 0.0,
        "index_name": "general_index",
    }


def _dedupe_context_items(items: list[dict], limit: int) -> list[dict]:
    deduped: list[dict] = []
    seen: set[str] = set()
    for item in items:
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        key = re.sub(r"\s+", " ", text).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _log_retrieved_chunks(query: str, items: list[dict]) -> None:
    for idx, item in enumerate(items, start=1):
        metadata = item.get("metadata") or {}
        dlog(
            "RAG",
            "Retrieved chunk",
            query=query[:100],
            rank=idx,
            chapter=metadata.get("chapter") or "",
            topic=metadata.get("topic") or "",
            chunk_type=metadata.get("type") or "",
            index_name=item.get("index_name") or "general_index",
            score=f"{float(item.get('score', 0.0)):.3f}",
            preview=str(item.get("text") or "")[:180],
        )


def _context_section_name(item: dict) -> str:
    metadata = item.get("metadata") or {}
    chunk_type = str(metadata.get("type") or "").strip().lower()
    if chunk_type in {"concept", "definition"}:
        return "Concept"
    if chunk_type == "example":
        return "Example"
    if chunk_type == "formula":
        return "Formula"
    if chunk_type == "question":
        return "Question Bank"
    return "Reference"



def _format_context_block(items: list[dict], summary_context: str = "") -> str:
    parts = ["[CONTEXT START]"]
    if summary_context:
        parts.append(f"Document Summary:\n{summary_context.strip()}")

    section_order = ["Concept", "Example", "Formula", "Question Bank", "Reference"]
    grouped: dict[str, list[dict]] = {name: [] for name in section_order}
    for item in items:
        grouped.setdefault(_context_section_name(item), []).append(item)

    chunk_number = 1
    for section in section_order:
        entries = grouped.get(section) or []
        if not entries:
            continue
        parts.append(f"{section}:")
        for item in entries:
            metadata = item.get("metadata") or {}
            labels = []
            if metadata.get("chapter"):
                labels.append(f"chapter={metadata['chapter']}")
            if metadata.get("topic"):
                labels.append(f"topic={metadata['topic']}")
            label_text = f" ({', '.join(labels)})" if labels else ""
            parts.append(f"- Chunk {chunk_number}{label_text}: {str(item.get('text') or '').strip()}")
            chunk_number += 1

    parts.append("[CONTEXT END]")
    return "\n\n".join(part for part in parts if part).strip()


def _is_no_info_response(answer: str) -> bool:
    lowered = str(answer or "").strip().lower()
    if not lowered:
        return True
    phrases = (
        "i could not find this in the provided study material",
        "i don't have enough information in the provided material",
        "i do not have enough information in the provided material",
        "not enough information in the provided material",
        "not found in the context",
        "not in the provided",
    )
    return any(phrase in lowered for phrase in phrases)


def _is_answer_grounded(answer: str, context: str, query: str) -> bool:
    cleaned_answer = clean_output(answer)
    if not cleaned_answer:
        return False
    if _is_no_info_response(cleaned_answer):
        return True
    if not str(context or "").strip():
        return True

    answer_terms = _grounding_terms(cleaned_answer)
    context_terms = _grounding_terms(context)
    query_terms = _grounding_terms(query)
    if not answer_terms or not context_terms:
        return False

    overlap = answer_terms.intersection(context_terms)
    required = max(1, min(3, len(query_terms) or 1))
    return len(overlap) >= required


def _build_cache_key(
    user_id: str,
    session_id: str,
    query: str,
    model_name: str,
    session_content_ref: str,
    task: str = "qa",
) -> str:
    raw = f"{user_id}:{session_id}:{query}:{model_name}:{session_content_ref}:{task or 'qa'}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _looks_like_summary_request(query: str) -> bool:
    text = str(query or "").strip().lower()
    if not text:
        return False

    summary_terms = (
        "summarize",
        "summarise",
        "summary",
        "overview",
        "key points",
        "main points",
        "gist",
        "short note",
    )
    return any(term in text for term in summary_terms)



def _infer_retrieval_task(task: str, query: str) -> str:
    normalized_task = str(task or "qa").strip().lower() or "qa"
    lowered = str(query or "").strip().lower()
    if normalized_task in {"quiz", "assessment", "summary", "lesson", "flashcards", "math", "translation"}:
        return normalized_task
    if _looks_like_summary_request(lowered):
        return "summary"
    if any(term in lowered for term in ("quiz", "mcq", "multiple choice", "test me")):
        return "quiz"
    if any(term in lowered for term in ("solve", "equation", "formula", "calculate", "derive")):
        return "math"
    if any(term in lowered for term in ("explain", "what is", "why", "how", "describe", "definition")):
        return "lesson"
    return normalized_task



def _select_context_top_k(query: str, task: str, summary_context: str = "") -> int:
    configured = min(max(3, int(get_rag_top_k(default=4) or 4)), 5)
    retrieval_task = _infer_retrieval_task(task, query)
    tuned = {
        "quiz": 3,
        "assessment": 3,
        "qa": 4,
        "lesson": 4,
        "flashcards": 4,
        "math": 4,
        "summary": 5,
        "translation": 4,
    }.get(retrieval_task, configured)
    if summary_context and retrieval_task == "summary":
        tuned = 5
    return min(5, max(3, tuned))



def _keyword_only_query(query: str) -> str:
    intent_words = {
        "explain",
        "describe",
        "definition",
        "define",
        "summarize",
        "summarise",
        "summary",
        "overview",
        "quiz",
        "practice",
        "question",
        "questions",
    }
    keywords = [token for token in dict.fromkeys(_grounding_terms(query)) if token not in intent_words]
    return " ".join(keywords[:6]).strip()



def _build_query_variants(query: str, task: str) -> list[str]:
    normalized_query = " ".join(str(query or "").strip().split())
    if not normalized_query:
        return []

    retrieval_task = _infer_retrieval_task(task, normalized_query)
    variants: list[str] = []

    def add_variant(value: str) -> None:
        cleaned = " ".join(str(value or "").strip().split())
        if cleaned and cleaned not in variants:
            variants.append(cleaned)

    add_variant(normalized_query)
    keyword_query = _keyword_only_query(normalized_query)
    add_variant(keyword_query)

    if keyword_query:
        if retrieval_task in {"qa", "lesson"}:
            add_variant(f"{keyword_query} definition")
            add_variant(f"{keyword_query} explanation example")
        elif retrieval_task in {"quiz", "assessment"}:
            add_variant(f"{keyword_query} key facts")
            add_variant(f"{keyword_query} practice questions")
        elif retrieval_task == "summary":
            add_variant(f"{keyword_query} summary key points")
            add_variant(f"{keyword_query} concise overview")
        elif retrieval_task == "math":
            add_variant(f"{keyword_query} formula")
            add_variant(f"{keyword_query} solved example")

    return variants[:4]



def _retrieve_context_items(
    query: str,
    *,
    task: str = "qa",
    filter_path: str | None = None,
    top_k: int = 4,
    search_k: int = 8,
) -> list[dict]:
    retrieval_task = _infer_retrieval_task(task, query)
    merged: dict[str, dict] = {}

    for variant_rank, variant in enumerate(_build_query_variants(query, retrieval_task)):
        variant_results = search(
            variant,
            filter_path=filter_path,
            top_k=max(top_k, 3),
            search_k=max(search_k, top_k * 2),
            task=retrieval_task,
            return_details=True,
        )
        for item in variant_results or []:
            normalized = _normalize_retrieval_item(item)
            text_key = re.sub(r"\s+", " ", normalized.get("text", "")).strip().lower()
            if not text_key:
                continue

            variant_bonus = max(0.0, 0.06 - (variant_rank * 0.01))
            normalized["score"] = float(normalized.get("score", 0.0) or 0.0) + variant_bonus
            existing = merged.get(text_key)
            if existing is None or float(normalized["score"]) >= float(existing.get("score", 0.0)):
                merged[text_key] = {**normalized, "matched_queries": [variant]}
            else:
                existing.setdefault("matched_queries", []).append(variant)

    ranked = sorted(
        merged.values(),
        key=lambda item: (
            float(item.get("score", 0.0)),
            len(item.get("matched_queries", [])),
            len(_grounding_terms(item.get("text", ""))),
        ),
        reverse=True,
    )
    return _dedupe_context_items(ranked, limit=top_k)


# -------------------------
# Core RAG Functions
# -------------------------
def generate_answer(
    query: str,
    user_id: str = "default",
    session_id: str = None,
    model_name: str = None,
    session_content_override=_CONTENT_UNSET,
    task: str = "qa",
) -> str:
    """Generate answer (non-streaming) with caching, history, and fallback."""
    t_start = time.perf_counter()
    if not session_id:
        session_id = f"{user_id}_default"
    normalized_task = str(task or "qa").strip().lower() or "qa"

    dlog(
        "RAG",
        "generate_answer called",
        user=user_id,
        session=session_id,
        query=query[:120],
        requested_model=model_name or "auto",
        task=normalized_task,
    )

    if session_content_override is _CONTENT_UNSET:
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
    else:
        session_content_ref = session_content_override

    resolved_content = None
    if session_content_ref:
        try:
            resolved_content = resolve_content_reference({"username": user_id}, session_content_ref)
        except Exception:
            resolved_content = None

    session_content_path = resolved_content["path"] if resolved_content else None
    cache_content_ref = resolved_content["content_id"] if resolved_content else session_content_ref

    summary_context = ""
    if session_content_path:
        try:
            summary_context = (get_summary(session_content_path) or "").strip()
        except Exception:
            summary_context = ""

    key = _build_cache_key(user_id, session_id, query, model_name, cache_content_ref, normalized_task)
    cached = get_cache(key)
    if cached:
        elapsed = (time.perf_counter() - t_start) * 1000
        dlog("RAG", "Cache HIT", elapsed_ms=f"{elapsed:.1f}ms")
        return cached["answer"]

    history_data = get_history(user_id, session_id)[-3:]
    last_question = history_data[-1]["question"] if history_data else ""
    enhanced_query = f"{query}. Context: {last_question}" if last_question and len(query) < 80 else query

    retrieval_task = _infer_retrieval_task(normalized_task, query)
    top_k = _select_context_top_k(query, retrieval_task, summary_context=summary_context)
    context_items = _retrieve_context_items(
        enhanced_query,
        task=retrieval_task,
        filter_path=session_content_path,
        top_k=top_k,
        search_k=max(8, top_k * 2),
    )
    _log_retrieved_chunks(query, context_items)

    raw_context = "\n".join(item.get("text", "") for item in context_items).strip()
    has_relevant_context = session_content_path or is_context_relevant(query, raw_context)
    context = _format_context_block(context_items, summary_context=summary_context) if has_relevant_context and (raw_context or summary_context) else ""

    history_text = "".join(
        [f"user: {h['question']}\nassistant: {h['answer']}\n" for h in history_data]
    )

    fallback_used = False
    if not context.strip():
        fallback_used = True
        answer = _GROUNDING_FALLBACK
    else:
        answer = generate_response(
            context=context,
            query=query,
            history=history_text,
            model_name=model_name,
            task=normalized_task,
        )

    if _is_no_info_response(answer):
        fallback_used = True
        answer = _GROUNDING_FALLBACK

    answer = clean_output(answer)
    if not _is_answer_grounded(answer, context, query):
        fallback_used = True
        answer = _GROUNDING_FALLBACK
    set_cache(key, {"answer": answer})
    save_chat(
        user_id,
        session_id,
        query,
        answer,
        session_content=session_content_ref,
        selected_content=cache_content_ref,
    )

    total_elapsed = (time.perf_counter() - t_start) * 1000
    dlog(
        "RAG",
        "generate_answer complete",
        elapsed_ms=f"{total_elapsed:.1f}ms",
        fallback_used=fallback_used,
        answer_chars=len(answer),
    )
    return answer


def generate_answer_stream(
    query,
    user_id="default",
    session_id=None,
    model_name=None,
    session_content_override=_CONTENT_UNSET,
    task: str = "qa",
):
    """Stream answer token-by-token (generator) with caching and fallback."""
    t_start = time.perf_counter()
    if not session_id:
        session_id = f"{user_id}_default"
    normalized_task = str(task or "qa").strip().lower() or "qa"

    if session_content_override is _CONTENT_UNSET:
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
    else:
        session_content_ref = session_content_override

    resolved_content = None
    if session_content_ref:
        try:
            resolved_content = resolve_content_reference({"username": user_id}, session_content_ref)
        except Exception:
            resolved_content = None

    session_content_path = resolved_content["path"] if resolved_content else None
    cache_content_ref = resolved_content["content_id"] if resolved_content else session_content_ref

    summary_context = ""
    if session_content_path:
        try:
            summary_context = (get_summary(session_content_path) or "").strip()
        except Exception:
            summary_context = ""

    key = _build_cache_key(user_id, session_id, query, model_name, cache_content_ref, normalized_task)
    cached = get_cache(key)
    if cached:
        save_chat(
            user_id,
            session_id,
            query,
            cached["answer"],
            session_content=session_content_ref,
            selected_content=cache_content_ref,
        )
        for token in cached["answer"].split():
            yield token + " "
        return

    history_data = get_history(user_id, session_id)[-3:]

    save_chat(
        user_id,
        session_id,
        query,
        "",
        session_content=session_content_ref,
        selected_content=cache_content_ref,
    )

    last_question = history_data[-1]["question"] if history_data else ""
    enhanced_query = f"{query}. Context: {last_question}" if last_question and len(query) < 80 else query

    retrieval_task = _infer_retrieval_task(normalized_task, query)
    top_k = _select_context_top_k(query, retrieval_task, summary_context=summary_context)
    context_items = _retrieve_context_items(
        enhanced_query,
        task=retrieval_task,
        filter_path=session_content_path,
        top_k=top_k,
        search_k=max(8, top_k * 2),
    )
    _log_retrieved_chunks(query, context_items)

    raw_context = "\n".join(item.get("text", "") for item in context_items).strip()
    has_relevant_context = session_content_path or is_context_relevant(query, raw_context)
    context = _format_context_block(context_items, summary_context=summary_context) if has_relevant_context and (raw_context or summary_context) else ""

    history_text = "".join(
        [f"user: {h['question']}\nassistant: {h['answer']}\n" for h in history_data]
    )

    if not context.strip():
        full_response = _GROUNDING_FALLBACK
        yield full_response
    else:
        full_response = ""
        for token in generate_response_stream(context, query, history_text, model_name, task=normalized_task):
            yield token
            full_response += token

        if _is_no_info_response(full_response):
            full_response = _GROUNDING_FALLBACK
        else:
            full_response = clean_output(full_response)
            if not _is_answer_grounded(full_response, context, query):
                full_response = _GROUNDING_FALLBACK
    set_cache(key, {"answer": full_response})
    save_chat(
        user_id,
        session_id,
        query,
        full_response,
        session_content=session_content_ref,
        selected_content=cache_content_ref,
    )

    elapsed = (time.perf_counter() - t_start) * 1000
    dlog("RAG", "generate_answer_stream complete", elapsed_ms=f"{elapsed:.1f}ms")


# -------------------------
# Retrieve knowledge chunks (lesson/quiz context)
# -------------------------
def retrieve_chunks(chapter: str, top_k: int = 5, filter_path: str | None = None):
    """
    Retrieve chapter-relevant chunks from the indexed documents.

    Strategy:
    1. If a selected content path is provided, scope retrieval to that file.
    2. Prefer chunks whose source path contains chapter keywords.
    3. Fall back to FAISS semantic search.
    """
    query = (chapter or "").strip()
    if not query:
        return []

    chapter_terms = {w for w in query.lower().replace("-", " ").split() if len(w) > 1}
    normalized_filter_path = os.path.normcase(os.path.normpath(str(filter_path or ""))) if filter_path else None

    source_matches = []
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        source_raw = str(doc.get("source") or "").strip()
        source = source_raw.lower()
        text = doc.get("text", "")
        if not source or not text:
            continue
        if normalized_filter_path and os.path.normcase(os.path.normpath(source_raw)) != normalized_filter_path:
            continue

        source_words = set(source.replace("\\", " ").replace("/", " ").replace("-", " ").split())
        overlap = len(chapter_terms.intersection(source_words))
        if overlap > 0 or normalized_filter_path:
            source_matches.append((overlap, text))

    if source_matches:
        source_matches.sort(reverse=True, key=lambda x: x[0])
        return [text for _, text in source_matches[:top_k]]

    return search(query, top_k=top_k, search_k=max(8, top_k * 2), task="lesson", filter_path=filter_path)
