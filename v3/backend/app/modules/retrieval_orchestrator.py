"""Compatibility-first multi-index + hybrid retrieval helpers.

This Step 8 slice keeps the existing FAISS-backed store intact while adding:
- logical multi-index planning (`curriculum`, `upload`, `session`, `artifact`)
- hybrid lexical + vector scoring
- detailed retrieval packets for future orchestration work
"""

from __future__ import annotations

import os
import re
from typing import Any, Iterable, Optional, Sequence

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(str(text or "").lower()) if len(token) > 1]


def infer_source_type(source: Optional[str]) -> str:
    normalized = str(source or "").replace("\\", "/").lower()
    if not normalized:
        return "general"
    if "/knowledge_base/" in normalized:
        return "curriculum"
    if "/app/uploads/" in normalized or "/uploads/" in normalized:
        return "upload"
    if any(marker in normalized for marker in ("learning_artifacts", "artifact", "flashcard", "lesson_plan", "assessment_papers", "quiz_results")):
        return "artifact"
    if any(marker in normalized for marker in ("chat_history", "session:", "/sessions/")):
        return "session"
    return "general"


def build_index_plan(task: str = "qa", filter_path: Optional[str] = None) -> list[str]:
    if filter_path:
        return ["selected_content"]

    normalized_task = str(task or "qa").strip().lower() or "qa"
    plans = {
        "qa": ["curriculum", "upload", "session", "artifact", "general"],
        "explanation": ["curriculum", "upload", "artifact", "session"],
        "summary": ["upload", "curriculum", "session"],
        "lesson": ["curriculum", "upload", "artifact", "session"],
        "quiz": ["curriculum", "artifact", "upload", "session"],
        "flashcards": ["curriculum", "artifact", "upload", "session"],
        "assessment": ["curriculum", "artifact", "upload", "session"],
        "translation": ["curriculum", "upload", "general"],
        "math": ["curriculum", "upload", "general"],
    }
    return plans.get(normalized_task, plans["qa"])


def build_logical_index_plan(task: str = "qa") -> list[str]:
    normalized_task = str(task or "qa").strip().lower() or "qa"
    plans = {
        "qa": ["concept_index", "summary_index", "qa_index"],
        "explanation": ["concept_index", "summary_index", "qa_index"],
        "summary": ["summary_index", "concept_index", "qa_index"],
        "lesson": ["concept_index", "summary_index", "qa_index"],
        "quiz": ["qa_index", "concept_index", "summary_index"],
        "flashcards": ["concept_index", "summary_index", "qa_index"],
        "assessment": ["qa_index", "concept_index", "summary_index"],
        "translation": ["concept_index", "summary_index", "general_index"],
        "math": ["formula_index", "concept_index", "summary_index"],
    }
    return plans.get(normalized_task, plans["qa"])


def _normalize_doc(doc: Any) -> dict[str, Any]:
    if isinstance(doc, dict):
        metadata = dict(doc.get("metadata") or {})
        return {
            "text": str(doc.get("text") or ""),
            "source": doc.get("source"),
            "index_name": doc.get("index_name") or metadata.get("index_name") or "general_index",
            "metadata": metadata,
        }
    return {"text": str(doc or ""), "source": None, "index_name": "general_index", "metadata": {}}


def _lexical_score(query: str, text: str, source: Optional[str]) -> tuple[float, list[str]]:
    query_terms = list(dict.fromkeys(_tokenize(query)))
    if not query_terms:
        return 0.0, []

    haystack = f"{source or ''} {text or ''}".lower()
    matched_terms = [term for term in query_terms if term in haystack]
    if not matched_terms:
        return 0.0, []

    overlap_ratio = len(matched_terms) / max(1, len(query_terms))
    phrase = str(query or "").strip().lower()
    phrase_boost = 0.35 if phrase and len(query_terms) > 1 and phrase in haystack else 0.0
    frequency_boost = min(0.25, sum(haystack.count(term) for term in matched_terms) * 0.03)
    return overlap_ratio + phrase_boost + frequency_boost, matched_terms


def _infer_query_intent(query: str) -> str:
    lowered = str(query or "").strip().lower()
    if any(term in lowered for term in ("summarize", "summarise", "summary", "overview", "key points")):
        return "summary"
    if any(term in lowered for term in ("quiz", "mcq", "multiple choice", "test me")):
        return "quiz"
    if any(term in lowered for term in ("solve", "equation", "formula", "calculate", "derive")):
        return "math"
    if any(term in lowered for term in ("explain", "what is", "why", "how", "describe", "definition")):
        return "explanation"
    return "qa"


def _metadata_text(metadata: dict[str, Any]) -> str:
    return " ".join(
        str(metadata.get(field) or "")
        for field in ("chapter", "topic", "type", "modality")
    ).strip()


def _normalize_path_for_compare(path: Optional[str]) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    return os.path.normcase(os.path.normpath(raw)).replace("\\", "/")


def hybrid_rank_results(
    query: str,
    docs: Sequence[Any],
    hit_indices: Optional[Iterable[int]] = None,
    hit_distances: Optional[Iterable[float]] = None,
    *,
    filter_path: Optional[str] = None,
    top_k: int = 4,
    task: str = "qa",
    source_types: Optional[Sequence[str]] = None,
) -> list[dict[str, Any]]:
    requested_task = str(task or "qa").strip().lower() or "qa"
    effective_task = _infer_query_intent(query) if requested_task in {"qa", "lesson"} else requested_task
    preferred_sources = set(source_types or build_index_plan(effective_task, filter_path))
    preferred_indexes = set(build_logical_index_plan(effective_task))
    normalized_filter_path = _normalize_path_for_compare(filter_path)
    score_map: dict[int, dict[str, Any]] = {}

    def ensure_entry(doc_index: int) -> Optional[dict[str, Any]]:
        if doc_index < 0 or doc_index >= len(docs):
            return None
        if doc_index in score_map:
            return score_map[doc_index]

        normalized = _normalize_doc(docs[doc_index])
        text = normalized["text"]
        source = normalized.get("source")
        if not text:
            return None
        if normalized_filter_path and _normalize_path_for_compare(source) != normalized_filter_path:
            return None

        entry = {
            "text": text,
            "source": source,
            "source_type": infer_source_type(source),
            "index_name": normalized.get("index_name", "general_index"),
            "metadata": normalized.get("metadata") or {},
            "vector_score": 0.0,
            "lexical_score": 0.0,
            "rank_bonus": 0.0,
            "score": 0.0,
            "matched_terms": [],
        }
        score_map[doc_index] = entry
        return entry

    distance_list = list(hit_distances) if hit_distances is not None else []
    hit_index_list = list(hit_indices) if hit_indices is not None else []
    for rank, raw_index in enumerate(hit_index_list):
        try:
            doc_index = int(raw_index)
        except (TypeError, ValueError):
            continue
        entry = ensure_entry(doc_index)
        if entry is None:
            continue

        distance = float(distance_list[rank]) if rank < len(distance_list) else 1.0
        entry["vector_score"] = max(entry["vector_score"], 1.0 / (1.0 + max(0.0, distance)))
        entry["rank_bonus"] = max(entry["rank_bonus"], max(0.0, 0.18 - (rank * 0.03)))

    for doc_index in range(len(docs)):
        entry = ensure_entry(doc_index)
        if entry is None:
            continue

        lexical_score, matched_terms = _lexical_score(query, entry["text"], entry.get("source"))
        entry["lexical_score"] = max(entry["lexical_score"], lexical_score)
        if matched_terms:
            entry["matched_terms"] = sorted(set([*entry["matched_terms"], *matched_terms]))

        metadata = entry.get("metadata") or {}
        metadata_score, metadata_terms = _lexical_score(query, _metadata_text(metadata), None)
        entry["metadata_score"] = max(float(entry.get("metadata_score", 0.0)), metadata_score)
        if metadata_terms:
            entry["matched_terms"] = sorted(set([*entry["matched_terms"], *metadata_terms]))

        if filter_path:
            source_bonus = 0.18
        elif entry["source_type"] in preferred_sources:
            source_bonus = 0.12
        elif entry["source_type"] == "general" and "general" in preferred_sources:
            source_bonus = 0.04
        else:
            source_bonus = -0.03

        index_name = str(entry.get("index_name") or "general_index")
        if index_name in preferred_indexes:
            index_bonus = 0.14
        elif index_name == "general_index":
            index_bonus = 0.01
        else:
            index_bonus = -0.02

        chunk_type = str(metadata.get("type") or "").strip().lower()
        type_bonus = 0.0
        if effective_task in {"lesson", "explanation", "qa"} and chunk_type in {"concept", "definition", "example"}:
            type_bonus = 0.12 if chunk_type != "example" else 0.07
        elif effective_task in {"quiz", "assessment"} and chunk_type == "question":
            type_bonus = 0.12
        elif effective_task == "math" and chunk_type == "formula":
            type_bonus = 0.16
        elif effective_task == "summary" and chunk_type in {"concept", "definition", "example"}:
            type_bonus = 0.09

        token_count = len(_tokenize(entry["text"]))
        noise_penalty = 0.0
        if token_count < 4:
            noise_penalty -= 0.10
        if token_count < 8 and not entry["matched_terms"]:
            noise_penalty -= 0.08

        entry["score"] = (
            (entry["lexical_score"] * 0.55)
            + (entry["metadata_score"] * 0.15)
            + (entry["vector_score"] * 0.30)
            + entry["rank_bonus"]
            + source_bonus
            + index_bonus
            + type_bonus
            + noise_penalty
        )

    ranked = sorted(
        score_map.values(),
        key=lambda item: (item["score"], item["lexical_score"], item["vector_score"]),
        reverse=True,
    )

    deduped: list[dict[str, Any]] = []
    seen_texts: set[str] = set()
    for item in ranked:
        text_key = item["text"].strip().lower()
        if not text_key or text_key in seen_texts:
            continue

        has_signal = (
            float(item.get("lexical_score", 0.0)) > 0.0
            or float(item.get("metadata_score", 0.0)) > 0.0
            or float(item.get("vector_score", 0.0)) >= 0.12
        )
        if not has_signal:
            continue

        seen_texts.add(text_key)
        deduped.append(item)
        if len(deduped) >= max(1, int(top_k or 1)):
            break

    return deduped


def build_context_packet(
    query: str,
    docs: Sequence[Any],
    hit_indices: Optional[Iterable[int]] = None,
    hit_distances: Optional[Iterable[float]] = None,
    *,
    filter_path: Optional[str] = None,
    top_k: int = 4,
    task: str = "qa",
    source_types: Optional[Sequence[str]] = None,
) -> dict[str, Any]:
    ranked = hybrid_rank_results(
        query,
        docs,
        hit_indices,
        hit_distances,
        filter_path=filter_path,
        top_k=top_k,
        task=task,
        source_types=source_types,
    )
    citations = [
        {
            "source": item.get("source"),
            "source_type": item.get("source_type", "general"),
        }
        for item in ranked
        if item.get("source")
    ]
    source_mix = sorted({item.get("source_type", "general") for item in ranked})
    avg_score = sum(float(item.get("score", 0.0)) for item in ranked) / max(1, len(ranked))
    return {
        "task": str(task or "qa"),
        "query": query,
        "context_chunks": [item.get("text", "") for item in ranked],
        "citations": citations,
        "confidence_score": round(avg_score, 3),
        "source_mix": source_mix,
    }
