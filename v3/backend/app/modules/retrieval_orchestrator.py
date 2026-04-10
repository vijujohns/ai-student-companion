"""Compatibility-first multi-index + hybrid retrieval helpers.

This Step 8 slice keeps the existing FAISS-backed store intact while adding:
- logical multi-index planning (`curriculum`, `upload`, `session`, `artifact`)
- hybrid lexical + vector scoring
- detailed retrieval packets for future orchestration work
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Iterable, Optional, Sequence

from .query_classifier import classify_query

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(str(text or "").lower()) if len(token) > 1]


def _normalized_text_key(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(text or "").lower())).strip()


def _contains_boilerplate_noise(text: str) -> bool:
    return bool(re.search(r"\b(?:document:|source:|chunk\s*\d+|page\s*\d+|diagram labels?)\b", str(text or ""), flags=re.IGNORECASE))


def _query_prefers_visual_labels(query: str) -> bool:
    lowered = str(query or "").lower()
    return any(term in lowered for term in ("diagram", "label", "labels", "figure", "marked", "shown", "image"))


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

    text_tokens = _tokenize(text)
    text_set = set(text_tokens)
    matched_terms = [term for term in query_terms if term in text_set]

    source_matches: list[str] = []
    if source:
        source_tokens = _tokenize(os.path.basename(str(source or "")))
        source_set = set(source_tokens)
        source_matches = [term for term in query_terms if term not in matched_terms and term in source_set]

    if not matched_terms and not source_matches:
        return 0.0, []

    overlap_ratio = len(matched_terms) / max(1, len(query_terms))
    normalized_query = " ".join(query_terms)
    normalized_text = " ".join(text_tokens)
    phrase_boost = 0.25 if normalized_query and len(query_terms) > 1 and normalized_query in normalized_text else 0.0
    frequency_boost = min(0.15, sum(text_tokens.count(term) for term in matched_terms) * 0.02)
    source_bonus = min(0.04, len(source_matches) * 0.02)
    return overlap_ratio + phrase_boost + frequency_boost + source_bonus, sorted(set([*matched_terms, *source_matches]))


def _infer_query_intent(query: str) -> str:
    lowered = str(query or "").strip().lower()
    if any(term in lowered for term in ("summarize", "summarise", "summary", "overview", "key points")):
        return "summary"
    if any(term in lowered for term in ("quiz", "mcq", "multiple choice", "test me")):
        return "quiz"

    query_type = classify_query(query)
    if query_type == "summary_structured":
        return "summary"
    if query_type == "math":
        return "math"
    if query_type in {"definition", "explanation", "list"}:
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


def semantic_similarity(text1: str, text2: str) -> float:
    tokens1 = _tokenize(text1)
    tokens2 = _tokenize(text2)
    if not tokens1 or not tokens2:
        return 0.0

    set1 = set(tokens1)
    set2 = set(tokens2)
    overlap = len(set1.intersection(set2))
    jaccard = overlap / max(1, len(set1.union(set2)))
    coverage = overlap / max(1, min(len(set1), len(set2)))
    phrase_boost = 0.08 if len(tokens1) > 1 and " ".join(tokens1) in " ".join(tokens2) else 0.0
    return min(1.0, (jaccard * 0.55) + (coverage * 0.45) + phrase_boost)


def _intent_type_bonus(intent: str, chunk_type: str) -> float:
    intent_key = str(intent or "qa").strip().lower() or "qa"
    chunk_key = str(chunk_type or "").strip().lower()
    bonus_map = {
        "qa": {"concept": 0.10, "definition": 0.10, "example": 0.05},
        "lesson": {"concept": 0.14, "definition": 0.14, "example": 0.07},
        "explanation": {"concept": 0.16, "definition": 0.16, "example": 0.08},
        "quiz": {"question": 0.18, "concept": 0.05},
        "assessment": {"question": 0.18, "concept": 0.05},
        "math": {"formula": 0.20, "concept": 0.08},
        "summary": {"concept": 0.10, "definition": 0.08, "example": 0.10},
    }
    return float((bonus_map.get(intent_key) or {}).get(chunk_key, 0.0))


def _debug_score(stage: str, item: dict[str, Any]) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    logger.debug(
        "retrieval_%s score=%.3f rerank=%.3f vector=%.3f lexical=%.3f metadata=%.3f semantic=%.3f type=%s source=%s preview=%s",
        stage,
        float(item.get("score", 0.0) or 0.0),
        float(item.get("rerank_score", 0.0) or 0.0),
        float(item.get("vector_score", 0.0) or 0.0),
        float(item.get("lexical_score", 0.0) or 0.0),
        float(item.get("metadata_score", 0.0) or 0.0),
        float(item.get("semantic_score", 0.0) or 0.0),
        str((item.get("metadata") or {}).get("type") or ""),
        str(item.get("source") or ""),
        str(item.get("text") or "")[:120],
    )


def rerank_results(query: str, items: list[dict]) -> list[dict]:
    query_intent = _infer_query_intent(query)
    query_terms = set(_tokenize(query))
    reranked: list[dict[str, Any]] = []

    for item in items:
        enriched = dict(item)
        metadata = dict(enriched.get("metadata") or {})
        chunk_type = str(metadata.get("type") or "").strip().lower()
        text = str(enriched.get("text") or "")
        semantic_score = max(
            float(enriched.get("vector_score", 0.0) or 0.0),
            float(enriched.get("embedding_similarity", 0.0) or 0.0),
            semantic_similarity(query, f"{text} {_metadata_text(metadata)}"),
        )
        text_matches = set(enriched.get("text_matched_terms", []))
        metadata_matches = set(enriched.get("metadata_matched_terms", []))
        metadata_only_match = not text_matches and bool(metadata_matches)
        key_concept_bonus = min(0.12, len(text_matches.intersection(query_terms)) * 0.03)
        semantic_bonus = 0.15 if semantic_score > 0.60 else semantic_score * 0.08
        rerank_score = (
            float(enriched.get("score", 0.0) or 0.0)
            + semantic_bonus
            + key_concept_bonus
            + _intent_type_bonus(query_intent, chunk_type)
        )
        if metadata_only_match and semantic_score < 0.40:
            rerank_score -= 0.12

        enriched["semantic_score"] = semantic_score
        enriched["rerank_score"] = rerank_score
        enriched["score"] = rerank_score
        _debug_score("rerank", enriched)
        reranked.append(enriched)

    return sorted(
        reranked,
        key=lambda item: (
            float(item.get("rerank_score", 0.0) or 0.0),
            float(item.get("lexical_score", 0.0) or 0.0),
            float(item.get("semantic_score", 0.0) or 0.0),
            float(item.get("vector_score", 0.0) or 0.0),
        ),
        reverse=True,
    )


def clean_context_chunks(
    query: str,
    ranked_chunks: Sequence[dict[str, Any]],
    *,
    max_chunks: int = 4,
) -> list[dict[str, Any]]:
    query_terms = set(_tokenize(query))
    query_type = classify_query(query)
    prefers_visual_labels = _query_prefers_visual_labels(query)
    strict_match_required = query_type in {"fact", "quote"}
    limit_cap = 10 if query_type == "summary_structured" else 5
    limit = max(1, min(int(max_chunks or 4), limit_cap))
    cleaned: list[dict[str, Any]] = []
    seen_texts: set[str] = set()

    prioritized = sorted(
        [dict(item) for item in ranked_chunks],
        key=lambda item: (
            len(item.get("text_matched_terms", []) or []),
            float(item.get("lexical_score", 0.0) or 0.0),
            float(item.get("score", 0.0) or 0.0),
            float(item.get("semantic_score", 0.0) or 0.0),
        ),
        reverse=True,
    )

    for item in prioritized:
        text = str(item.get("text") or "").strip()
        if not text:
            continue

        text_key = _normalized_text_key(text)
        if not text_key or text_key in seen_texts:
            continue
        if any(semantic_similarity(text_key, seen) >= 0.94 for seen in seen_texts):
            continue

        metadata = dict(item.get("metadata") or {})
        tokens = _tokenize(text)
        text_matches = list(item.get("text_matched_terms", []))
        metadata_matches = list(item.get("metadata_matched_terms", []))
        lexical_score = float(item.get("lexical_score", 0.0) or 0.0)
        semantic_score = float(item.get("semantic_score", 0.0) or 0.0)
        overall_score = float(item.get("score", 0.0) or 0.0)
        metadata_score = float(item.get("metadata_score", 0.0) or 0.0)
        overlap = query_terms.intersection(set(tokens))
        has_boilerplate = _contains_boilerplate_noise(text)
        is_ocr_like = str(metadata.get("modality") or "").lower() == "ocr" or bool(metadata.get("is_diagram_label"))
        metadata_only_match = not overlap and not text_matches and bool(metadata_matches) and metadata_score >= 0.12

        if len(tokens) < 8 and lexical_score < 0.25 and len(text_matches) < 2:
            continue
        if metadata_only_match:
            continue
        if has_boilerplate and lexical_score < 0.35 and len(overlap) < 2:
            continue
        if is_ocr_like and query_type == "summary_structured" and semantic_score < 0.70 and lexical_score < 0.35:
            continue
        if is_ocr_like and not prefers_visual_labels and lexical_score < 0.30 and len(overlap) < 2 and semantic_score < 0.55:
            continue

        if strict_match_required:
            has_signal = (len(text_matches) >= 2) or (len(overlap) >= 2) or lexical_score >= 0.28 or semantic_score >= 0.58
        else:
            has_signal = bool(text_matches) or bool(overlap) or lexical_score >= 0.18 or semantic_score >= 0.40

        if not has_signal:
            continue
        if overall_score < 0.18 and lexical_score < 0.18 and semantic_score < 0.40:
            continue

        item["has_strong_match"] = (
            not has_boilerplate and (
                lexical_score >= (0.38 if strict_match_required else 0.32)
                or len(text_matches) >= (2 if strict_match_required else 1)
                or len(overlap) >= (2 if strict_match_required else 1)
                or semantic_score >= 0.65
            )
        )
        seen_texts.add(text_key)
        cleaned.append(item)
        if len(cleaned) >= limit:
            break

    return cleaned


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
    query_type = classify_query(query)
    prefers_visual_labels = _query_prefers_visual_labels(query)
    preferred_sources = set(source_types or build_index_plan(effective_task, filter_path))
    preferred_indexes = set(build_logical_index_plan(effective_task))
    effective_top_k = max(8, int(top_k or 1)) if query_type == "summary_structured" else max(1, int(top_k or 1))
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
            "metadata_score": 0.0,
            "semantic_score": 0.0,
            "rank_bonus": 0.0,
            "rerank_score": 0.0,
            "score": 0.0,
            "matched_terms": [],
            "text_matched_terms": [],
            "metadata_matched_terms": [],
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
            entry["text_matched_terms"] = sorted(set([*entry["text_matched_terms"], *matched_terms]))
            entry["matched_terms"] = sorted(set([*entry["matched_terms"], *matched_terms]))

        metadata = entry.get("metadata") or {}
        metadata_score, metadata_terms = _lexical_score(query, _metadata_text(metadata), None)
        entry["metadata_score"] = max(float(entry.get("metadata_score", 0.0)), metadata_score)
        if metadata_terms:
            entry["metadata_matched_terms"] = sorted(set([*entry["metadata_matched_terms"], *metadata_terms]))
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
        type_bonus = _intent_type_bonus(effective_task, chunk_type)
        if query_type == "summary_structured":
            if chunk_type in {"concept", "definition"}:
                type_bonus += 0.06
            elif chunk_type == "example":
                type_bonus += 0.02

        semantic_score = semantic_similarity(query, f"{entry['text']} {_metadata_text(metadata)}")
        entry["semantic_score"] = max(float(entry.get("semantic_score", 0.0) or 0.0), semantic_score)
        semantic_bonus = 0.08 if semantic_score > 0.65 else 0.0

        token_count = len(_tokenize(entry["text"]))
        noise_penalty = 0.0
        has_boilerplate = _contains_boilerplate_noise(entry["text"])
        is_ocr_like = str(metadata.get("modality") or "").lower() == "ocr" or bool(metadata.get("is_diagram_label"))
        text_matches = list(entry.get("text_matched_terms") or [])
        metadata_matches = list(entry.get("metadata_matched_terms") or [])
        metadata_only_match = not text_matches and bool(metadata_matches) and entry["metadata_score"] >= 0.12 and entry["lexical_score"] < 0.10
        if token_count < 5:
            noise_penalty -= 0.20
        elif token_count < 8:
            noise_penalty -= 0.10
        if token_count < 20 and not text_matches and entry["lexical_score"] < 0.12:
            noise_penalty -= 0.10
        if not text_matches and entry["vector_score"] < 0.12 and entry["metadata_score"] < 0.08:
            noise_penalty -= 0.16
        if metadata_only_match:
            noise_penalty -= 0.10
        if has_boilerplate:
            noise_penalty -= 0.10
        if is_ocr_like and not prefers_visual_labels:
            noise_penalty -= 0.12 if query_type == "summary_structured" else 0.06
        if query_type in {"fact", "quote"} and entry["lexical_score"] < 0.22 and len(entry["matched_terms"]) < 2:
            noise_penalty -= 0.06

        entry["score"] = (
            (entry["lexical_score"] * 0.45)
            + (entry["metadata_score"] * 0.10)
            + (entry["vector_score"] * 0.30)
            + (entry["semantic_score"] * 0.10)
            + entry["rank_bonus"]
            + source_bonus
            + index_bonus
            + type_bonus
            + semantic_bonus
            + noise_penalty
        )
        _debug_score("initial", entry)

    ranked = sorted(
        score_map.values(),
        key=lambda item: (item["score"], item["semantic_score"], item["vector_score"], item["lexical_score"]),
        reverse=True,
    )
    ranked = rerank_results(query, ranked)

    return clean_context_chunks(query, ranked, max_chunks=effective_top_k)


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
    ranked = clean_context_chunks(query, ranked, max_chunks=max(1, min(int(top_k or 1), 5)))
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
        "has_strong_match": any(bool(item.get("has_strong_match")) for item in ranked),
        "chunk_scores": [round(float(item.get("score", 0.0) or 0.0), 3) for item in ranked],
    }
