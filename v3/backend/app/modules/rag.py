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
from functools import lru_cache
from typing import Any, Callable, List

from .answer_formatter import clean_answer as clean_presented_answer, strict_format_answer
from .cache import get_cache, set_cache
from .db import get_connection
from .faiss_store import documents, search
from .file_management import resolve_content_reference
from .history import get_history, save_chat
from .ingestion import chunk_text, extract_ocr_text_from_pdf, extract_text_from_pdf, get_summary
from .model_manager import generate_response, generate_response_stream
from .query_classifier import classify_query as shared_classify_query
from ..core.config_loader import get_app_env, get_rag_config, get_rag_top_k, is_dev
from ..core.debug_logger import dlog, dwarn


_CONTENT_UNSET = object()
_GROUNDING_FALLBACK = "I don't have enough information in the provided material."
_SELECTED_MATERIAL_FALLBACK = "This is not clearly mentioned in the selected material. Try selecting a more relevant chapter or ask in Explorer mode."
_GROUNDING_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "what", "which", "who", "when", "where",
    "why", "how", "this", "that", "these", "those", "and", "or", "but", "for", "with", "from",
    "into", "about", "your", "their", "them", "then", "than", "have", "has", "had", "does", "did",
    "not", "can", "could", "would", "should", "using", "used", "only", "based", "provided", "material",
    "study", "chunk", "answer",
}
_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")
_ANSWER_FORMAT_CACHE_VERSION = "2026-04-09-rag-quality-v2"
MAX_CONTEXT_TOKENS = 1200
_FOLLOW_UP_TERMS = {"this", "that", "it", "these", "those"}
_GENERIC_CONFIRMATIONS = {"yes", "yeah", "yes please", "ok", "okay", "sure", "continue"}
_DEFAULT_FORMATTING_RULES = {
    "formatter_order": ["compare", "list", "explain", "definition"],
    "intent_patterns": {
        "compare": [
            r"\bcompare\b",
            r"\bdifference between\b",
            r"\bdistinguish between\b",
            r"\bcontrast\b",
        ],
        "list": [
            r"^(?:list|name|show|give)\b",
            r"^(?:what are|which are)\b",
        ],
        "explain": [
            r"^(?:explain|describe|summari[sz]e|tell me about)\b",
            r"^(?:how|why)\b",
        ],
        "definition": [
            r"^(?:what|who|when|where|which)\s+(?:is|are|was|were)\b",
            r"^define\b",
        ],
    },
    "cleanup_markers": [
        "provided context",
        "provided material",
        "document summary",
        "context start",
        "context end",
        "reference:",
    ],
    "labels": {
        "simple_meaning": "Simple meaning",
        "key_points": "Key points",
        "summary": "In short",
    },
    "max_points": 4,
}


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


def classify_query(query: str) -> str:
    return shared_classify_query(query)


def _plain_context_text(context: str) -> str:
    flattened = re.sub(r"\s+", " ", str(context or "")).strip()
    plain_context = re.sub(r"\[(?:CONTEXT START|CONTEXT END)\]", " ", flattened, flags=re.IGNORECASE)
    plain_context = re.sub(r"\b(?:Document Summary|Concept|Example|Formula|Question Bank|Reference):", " ", plain_context)
    return re.sub(r"\s+", " ", plain_context).strip()


def _context_domain_signal(query: str, context: str) -> tuple[float, str]:
    lowered_query = str(query or "").lower()
    lowered_context = str(context or "").lower()
    domain_rules = (
        (
            {"pi", "π", "pie", "circle", "radius", "diameter", "circumference", "3.14", "area"},
            "The study context is about mathematics and circles, so interpret ambiguous terms in that math sense (Pi, not dessert).",
        ),
        (
            {"sound", "wave", "frequency", "amplitude", "pitch", "loudness", "wavelength", "vibration", "medium"},
            "The study context is about physics and sound waves.",
        ),
        (
            {"triangle", "hypotenuse", "pythagoras", "theorem", "right angle", "right-angled", "side lengths"},
            "The study context is about geometry and triangles.",
        ),
    )

    best_score = 0.0
    best_hint = ""
    for keywords, hint in domain_rules:
        context_hits = sum(1 for keyword in keywords if keyword in lowered_context)
        if context_hits == 0:
            continue
        query_hits = sum(1 for keyword in keywords if keyword in lowered_query)
        score = min(1.0, (context_hits / 4.0) + (0.20 if query_hits else 0.0))
        if any(phrase in lowered_query for phrase in ("what is pi", "what is pie")) and any(term in lowered_context for term in ("circle", "radius", "diameter", "circumference", "3.14")):
            score = max(score, 0.95)
        if score > best_score:
            best_score = score
            best_hint = hint
    return best_score, best_hint


def get_context_confidence(query: str, context: str) -> float:
    plain_context = _plain_context_text(context)
    if not plain_context:
        return 0.0

    query_type = classify_query(query)
    query_terms = _grounding_terms(query)
    context_terms = _grounding_terms(plain_context)
    meaningful_sentences = [
        sentence
        for sentence in _split_sentences(plain_context)
        if len(_grounding_terms(sentence)) >= 3 and len(sentence.split()) >= 6
    ]
    if not meaningful_sentences:
        return 0.0

    overlap = query_terms.intersection(context_terms)
    overlap_score = len(overlap) / max(1, len(query_terms)) if query_terms else 0.0
    semantic_score = _semantic_grounding_similarity(query, plain_context) if query_terms else 0.0
    length_score = min(1.0, len(plain_context) / 450.0)
    sentence_score = min(1.0, len(meaningful_sentences) / 3.0)

    definition_signal = 0.0
    for term in sorted(query_terms, key=len, reverse=True):
        if len(term) < 3:
            continue
        if re.search(rf"\b{re.escape(term)}\b\s+(?:is|are|was|were|means|refers to|describes|represents)\b", plain_context, flags=re.IGNORECASE):
            definition_signal = 1.0
            break

    domain_score, _ = _context_domain_signal(query, plain_context)
    confidence = (
        (overlap_score * 0.35)
        + (semantic_score * 0.20)
        + (sentence_score * 0.15)
        + (length_score * 0.10)
        + (max(definition_signal, domain_score) * 0.20)
    )

    has_summary = "document summary" in str(context or "").lower()
    if has_summary and _is_follow_up_query(query):
        confidence = max(confidence, 0.55)

    if query_type in {"definition", "explanation", "math", "fact", "quote"} and definition_signal == 0.0 and domain_score < 0.6 and len(plain_context) < 180 and overlap_score < 0.75:
        confidence *= 0.55

    if query_type in {"definition", "explanation", "math"} and domain_score >= 0.7:
        confidence = max(confidence, 0.65)
    if query_type in {"fact", "quote"} and len(overlap) >= 2:
        confidence = max(confidence, 0.60)

    return round(max(0.0, min(1.0, confidence)), 3)


def has_strong_context_match(query: str, context: str) -> bool:
    plain_context = _plain_context_text(context)
    if not plain_context:
        return False

    query_type = classify_query(query)
    query_terms = _grounding_terms(query)
    if not query_terms:
        return False

    context_terms = _grounding_terms(plain_context)
    overlap = query_terms.intersection(context_terms)
    lexical_ratio = len(overlap) / max(1, len(query_terms))
    phrase_match = any(re.search(rf"\b{re.escape(term)}\b", plain_context, flags=re.IGNORECASE) for term in query_terms)
    domain_score, _ = _context_domain_signal(query, plain_context)
    has_summary = "document summary" in str(context or "").lower()
    summary_backed_follow_up = has_summary and (_is_follow_up_query(query) or any(term in str(query or "").lower() for term in ("example", "examples", "real world")))

    if query_type in {"fact", "quote"}:
        return summary_backed_follow_up or (
            (phrase_match and (lexical_ratio >= 0.35 or len(overlap) >= 2))
            or lexical_ratio >= 0.60
            or len(overlap) >= 2
            or domain_score >= 0.80
        )

    return (
        phrase_match
        or lexical_ratio >= 0.5
        or len(overlap) >= min(2, len(query_terms))
        or domain_score >= 0.70
        or summary_backed_follow_up
    )


def is_context_strong(query: str, context: str) -> bool:
    return get_context_confidence(query, context) > 0.6


def clean_output(text: str) -> str:
    """Remove unwanted patterns, duplicate lines, and repeated words while preserving markdown callouts."""
    text = str(text or "")
    stop_markers = ["Question:", "Answer:", "User:", "assistant:", "Q:", "A:"]
    for marker in stop_markers:
        if marker in text:
            text = text.split(marker)[0]

    structured_markdown = any(token in text for token in ("\n>", "\n- ", "\n1. ", "]("))
    if structured_markdown:
        cleaned_lines = []
        seen = set()
        for raw_line in text.replace("\r", "\n").split("\n"):
            line = re.sub(r"[ \t]+", " ", raw_line).rstrip()
            normalized = line.strip()
            if not normalized:
                if cleaned_lines and cleaned_lines[-1] != "":
                    cleaned_lines.append("")
                continue
            key = normalized.lower()
            if key in seen and not normalized.startswith(">"):
                continue
            seen.add(key)
            cleaned_lines.append(normalized)
        return "\n".join(cleaned_lines).strip()

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    unique_lines = []
    for line in lines:
        if line not in unique_lines:
            unique_lines.append(line)
    text = " ".join(unique_lines)

    words = text.split()
    cleaned_words = [w for i, w in enumerate(words) if i == 0 or w != words[i - 1]]
    return " ".join(cleaned_words).strip()


def _is_short_fact_query(query: str) -> bool:
    lowered = " ".join(str(query or "").strip().lower().split())
    if not lowered:
        return False

    if lowered.startswith("how many "):
        return len(lowered.split()) <= 9

    if any(term in lowered for term in ("explain", "why", "how ", "describe", "compare", "difference", "example", "examples")):
        return False
    starters = ("who ", "what ", "when ", "where ", "which ", "define ", "tell me ", "name ", "list ")
    return len(lowered.split()) <= 8 and lowered.startswith(starters)


def _merge_rule_block(defaults: dict[str, Any], overrides: Any) -> dict[str, Any]:
    merged = dict(defaults)
    if not isinstance(overrides, dict):
        return merged

    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        elif isinstance(value, list):
            merged[key] = list(value)
        else:
            merged[key] = value
    return merged


@lru_cache(maxsize=1)
def _get_rag_behavior_rules() -> dict[str, Any]:
    rag_cfg = get_rag_config()
    return _merge_rule_block(_DEFAULT_FORMATTING_RULES, rag_cfg.get("formatting"))


def _formatting_rules() -> dict[str, Any]:
    return _get_rag_behavior_rules()


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = re.sub(r"\s+", " ", str(item or "")).strip(" ,.;:-")
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


def _title_case_phrase(text: str) -> str:
    normalized = " ".join(str(text or "").strip().split())
    if not normalized:
        return "Topic"

    small_words = {"of", "the", "and", "to", "in", "for", "on", "a", "an", "vs", "with"}
    words: list[str] = []
    for index, word in enumerate(normalized.split()):
        lowered_word = word.lower()
        if word.isupper() and len(word) <= 6:
            words.append(word)
        elif index > 0 and lowered_word in small_words:
            words.append(lowered_word)
        else:
            words.append(lowered_word.capitalize())
    return " ".join(words) or "Topic"


def _split_sentences(text: str) -> list[str]:
    normalized = str(text or "").replace("...", ". ")
    return [segment.strip(" ,") for segment in re.split(r"(?<=[.!?])\s+", normalized) if segment.strip()]


def _estimate_token_count(text: str) -> int:
    return len(_TOKEN_RE.findall(str(text or "")))


def _truncate_text_to_token_budget(text: str, max_tokens: int) -> str:
    content = str(text or "").strip()
    if not content or max_tokens <= 0:
        return ""
    if _estimate_token_count(content) <= max_tokens:
        return content

    words: list[str] = []
    token_count = 0
    for word in content.split():
        word_tokens = max(1, len(_TOKEN_RE.findall(word)))
        if token_count + word_tokens > max_tokens:
            break
        words.append(word)
        token_count += word_tokens
    return " ".join(words).strip()


def _limit_context_items_to_budget(
    items: list[dict],
    summary_context: str = "",
    max_tokens: int = MAX_CONTEXT_TOKENS,
) -> tuple[list[dict], str, int]:
    trimmed_summary = str(summary_context or "").strip()
    if trimmed_summary and _estimate_token_count(trimmed_summary) > max_tokens // 3:
        trimmed_summary = _truncate_text_to_token_budget(trimmed_summary, max_tokens // 3)

    remaining = max_tokens - _estimate_token_count(trimmed_summary)
    limited_items: list[dict] = []
    for item in items:
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        token_count = _estimate_token_count(text)
        if token_count <= max(0, remaining):
            limited_items.append(item)
            remaining -= token_count
        else:
            break

    if not limited_items and items:
        first_item = dict(items[0])
        first_item["text"] = _truncate_text_to_token_budget(str(first_item.get("text") or ""), max(120, max_tokens // 2))
        if str(first_item.get("text") or "").strip():
            limited_items = [first_item]

    total_tokens = _estimate_token_count(trimmed_summary) + sum(_estimate_token_count(item.get("text", "")) for item in limited_items)
    return limited_items, trimmed_summary, total_tokens


def _is_follow_up_query(query: str) -> bool:
    normalized = " ".join(str(query or "").strip().lower().split())
    if not normalized:
        return False
    query_words = set(re.findall(r"[a-z]+", normalized))
    if query_words.intersection(_FOLLOW_UP_TERMS):
        return True
    return len(query_words) <= 4 and normalized in {"why", "how", "explain more", "tell me more", "what about that"}


def _apply_user_level_guidance(
    query: str,
    user_level: str = "beginner",
    allow_general_knowledge: bool = False,
    domain_hint: str = "",
) -> str:
    normalized_query = str(query or "").strip()
    level = str(user_level or "beginner").strip().lower() or "beginner"
    guidance = {
        "beginner": "Explain in simple language and include one short, concrete example when helpful.",
        "intermediate": "Give a balanced explanation with clear reasoning and one concise example when helpful.",
        "advanced": "Give a detailed explanation using precise concepts and deeper reasoning where relevant.",
    }.get(level, "Explain clearly and match the student's level.")

    if domain_hint:
        guidance = f"{guidance} {domain_hint}"

    if allow_general_knowledge:
        guidance = (
            f"{guidance} If the retrieved study context is weak or incomplete, answer using reliable general knowledge. "
            "Do not mention missing context, provided material, or chunks."
        )

    return f"{normalized_query}\n\nTutor guidance: {guidance}" if normalized_query else guidance


def _semantic_grounding_similarity(text1: str, text2: str) -> float:
    terms1 = _grounding_terms(text1)
    terms2 = _grounding_terms(text2)
    if not terms1 or not terms2:
        return 0.0

    overlap = len(terms1.intersection(terms2))
    jaccard = overlap / max(1, len(terms1.union(terms2)))
    coverage = overlap / max(1, min(len(terms1), len(terms2)))
    return min(1.0, (jaccard * 0.45) + (coverage * 0.55))


def _grounding_metrics(answer: str, context: str, query: str) -> dict[str, float]:
    answer_terms = _grounding_terms(answer)
    context_terms = _grounding_terms(context)
    query_terms = _grounding_terms(query)
    overlap = answer_terms.intersection(context_terms)
    required = max(1, min(3, len(query_terms) or 1))
    semantic_score = _semantic_grounding_similarity(answer, context)
    query_alignment = len(answer_terms.intersection(query_terms)) / max(1, len(query_terms)) if query_terms else 0.0
    confidence = max(
        len(overlap) / max(1, required),
        semantic_score,
        query_alignment,
    )
    return {
        "overlap_count": float(len(overlap)),
        "required": float(required),
        "semantic_score": float(semantic_score),
        "query_alignment": float(query_alignment),
        "confidence": float(min(1.0, confidence)),
    }


def _flatten_context_for_presentation(context: str) -> str:
    text = str(context or "")
    text = text.replace("[CONTEXT START]", " ").replace("[CONTEXT END]", " ")
    text = re.sub(r"\b(?:Document Summary|Concept|Example|Formula|Question Bank|Reference):", " ", text)
    text = text.replace("\n- ", ". ")
    text = text.replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def _clean_presentation_fragment(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"\(chunk\s*\d+\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bchunk\s*\d+\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bstep\s*\d+\s*[:.-]?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\blet['’]s (?:look at|break down|find out|find the answer(?: together)?)\b[^.?!]*[.?!]?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\baccording to the [^.?!:]*[:,-]?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\baccording to [^.?!:]*[:,-]?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'"[^"]*(?:summary|notes|reference|context)[^"]*"', "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("provided context", "").replace("provided material", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,:-")
    return cleaned


def _normalize_sentence_for_display(sentence: str) -> str:
    cleaned = _clean_presentation_fragment(sentence)
    if not cleaned or len(cleaned.split()) < 4:
        return ""
    if cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    if not cleaned.endswith((".", "!", "?")):
        cleaned += "."
    return cleaned


def _extract_topic_from_query(query: str) -> str:
    normalized = " ".join(str(query or "").strip().split())
    if not normalized:
        return "Topic"

    patterns = (
        r"^(?:explain|describe|summari[sz]e|tell me about)\s+(.+)$",
        r"^(?:what are|what is|list|show|name)\s+(.+)$",
        r"^(?:compare|difference between|distinguish between|contrast)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, normalized, flags=re.IGNORECASE)
        if match:
            normalized = match.group(1)
            break

    return _title_case_phrase(normalized.strip(" ?.!"))


def _extract_presentable_sentences(answer: str, context: str) -> list[str]:
    combined = " ".join(part for part in (str(answer or ""), _flatten_context_for_presentation(context)) if part)
    sentences: list[str] = []
    seen: set[str] = set()
    cleanup_markers = tuple(str(marker).lower() for marker in _formatting_rules().get("cleanup_markers", []))
    for segment in _split_sentences(combined):
        cleaned = _normalize_sentence_for_display(segment)
        lowered = cleaned.lower()
        if not cleaned:
            continue
        if any(marker in lowered for marker in cleanup_markers):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        sentences.append(cleaned)
    return sentences


def _extract_list_items(answer: str, context: str) -> list[str]:
    items: list[str] = []
    blocked_prefixes = ("in the ", "on the ", "we can ", "we see ", "there are ", "additionally", "also ")

    for source in (answer, context):
        text = str(source or "")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.startswith(("- ", "* ", "• ")):
                items.append(line[2:].strip())

        for sentence in _split_sentences(text):
            candidates = [sentence.split(":", 1)[1]] if ":" in sentence else [sentence]
            for candidate in candidates:
                normalized = re.sub(r"^[^.?!:]*\b(?:includes?|such as|are|is|has(?: the following)?|consists of|listed as)\b[:\s-]*", "", candidate, flags=re.IGNORECASE)
                normalized = re.sub(r"\s+-\s+", ", ", normalized)
                normalized = re.sub(r"\s+(?:and|or)\s+", ", ", normalized, flags=re.IGNORECASE)
                if "," not in normalized and ";" not in normalized and " and " not in normalized.lower():
                    continue

                for part in re.split(r"[,;•]+", normalized):
                    cleaned = _clean_presentation_fragment(part)
                    cleaned = re.sub(r"^(?:the|a|an)\s+", "", cleaned, flags=re.IGNORECASE)
                    lowered = cleaned.lower()
                    if not cleaned or '"' in cleaned or "'" in cleaned:
                        continue
                    if any(lowered.startswith(prefix) for prefix in blocked_prefixes):
                        continue
                    if 1 < len(cleaned.split()) <= 8:
                        items.append(_title_case_phrase(cleaned) if cleaned.islower() else cleaned)

    return _dedupe_preserve_order(items)[:8]


def _detect_query_intent(query: str) -> str:
    normalized = " ".join(str(query or "").strip().lower().split())
    if not normalized:
        return "qa"

    if normalized.startswith("how many "):
        return "definition"

    intent_patterns = _formatting_rules().get("intent_patterns", {})
    for intent in ("compare",):
        for pattern in intent_patterns.get(intent, []):
            if re.search(pattern, normalized, flags=re.IGNORECASE):
                return intent

    query_type = classify_query(query)
    if query_type == "list":
        return "list"
    if query_type in {"explanation", "math"}:
        return "explain"
    if query_type in {"fact", "quote"}:
        return "fact"
    if query_type == "definition" or _is_short_fact_query(query):
        return "definition"
    return "qa"


def _extract_compare_targets(query: str) -> tuple[str, str] | None:
    normalized = " ".join(str(query or "").strip().split())
    patterns = (
        r"compare\s+(.+?)\s+(?:and|with|vs\.?|versus)\s+(.+)$",
        r"(?:difference between|distinguish between|contrast)\s+(.+?)\s+(?:and|with)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            left = match.group(1).strip(" ?.!,-")
            right = match.group(2).strip(" ?.!,-")
            if left and right:
                return left, right
    return None


def generic_definition_formatter(query: str, answer: str, context: str, *, intent: str | None = None) -> str | None:
    if (intent or _detect_query_intent(query)) != "definition":
        return None
    polished = _polish_short_fact_answer(answer, query, context)
    return polished if polished else None


def generic_list_formatter(query: str, answer: str, context: str, *, intent: str | None = None) -> str | None:
    if (intent or _detect_query_intent(query)) != "list":
        return None

    items = _extract_list_items(answer, context)
    if not items:
        return None

    summary_label = str((_formatting_rules().get("labels") or {}).get("summary", "In short"))
    title = _extract_topic_from_query(query)
    summary_candidates = _extract_presentable_sentences(answer, context)
    summary = summary_candidates[0] if summary_candidates else "The selected material highlights the key points related to this question."
    lines = [
        f"## {title}",
        "",
        *(f"- {item}" for item in items[:6]),
        "",
        f"> **{summary_label}:** {summary}",
    ]
    return "\n".join(lines).strip()


def generic_compare_formatter(query: str, answer: str, context: str, *, intent: str | None = None) -> str | None:
    if (intent or _detect_query_intent(query)) != "compare":
        return None

    targets = _extract_compare_targets(query)
    if not targets:
        return None

    left_topic, right_topic = targets
    combined = " ".join(part for part in (str(answer or ""), _flatten_context_for_presentation(context)) if part)

    def collect_points(subject: str) -> list[str]:
        subject_pattern = re.compile(re.escape(subject), flags=re.IGNORECASE)
        points: list[str] = []
        for sentence in _split_sentences(combined):
            if subject.lower() not in sentence.lower():
                continue
            trimmed = subject_pattern.sub("", sentence)
            trimmed = re.sub(r"\b(?:while|whereas|however)\b", ",", trimmed, flags=re.IGNORECASE)
            trimmed = re.sub(r"\s+(?:and|but)\s+", ", ", trimmed, flags=re.IGNORECASE)
            for fragment in re.split(r"[,;]+", trimmed):
                cleaned = _clean_presentation_fragment(fragment)
                cleaned = re.sub(r"^(?:the|a|an)\s+", "", cleaned, flags=re.IGNORECASE)
                if cleaned and cleaned.lower() not in {left_topic.lower(), right_topic.lower()}:
                    points.append(cleaned)
        return _dedupe_preserve_order(points)[:4]

    def pick_label(left: str, right: str, index: int) -> str:
        filler = {"more", "less", "higher", "lower", "better", "best", "worse", "limited", "improved", "main", "important"}
        skip_tokens = _GROUNDING_STOPWORDS.union(filler)
        left_tokens = [token for token in _TOKEN_RE.findall(str(left or "").lower()) if len(token) > 2 and token not in skip_tokens]
        right_tokens = [token for token in _TOKEN_RE.findall(str(right or "").lower()) if len(token) > 2 and token not in skip_tokens]
        common = [token for token in left_tokens if token in right_tokens]
        if common:
            return _title_case_phrase(common[-1])

        candidate = right_tokens[-1] if right_tokens else left_tokens[-1] if left_tokens else ""
        if candidate.endswith("s") and len(candidate) > 4:
            candidate = candidate[:-1]
        return _title_case_phrase(candidate) if candidate else f"Point {index + 1}"

    left_points = collect_points(left_topic)
    right_points = collect_points(right_topic)
    if not left_points and not right_points:
        return None

    row_count = max(2, min(max(len(left_points), len(right_points)), 5))
    rows = []
    for index in range(row_count):
        left_value = left_points[index] if index < len(left_points) else "—"
        right_value = right_points[index] if index < len(right_points) else "—"
        rows.append((pick_label(left_value, right_value, index), left_value or "—", right_value or "—"))

    summary_label = str((_formatting_rules().get("labels") or {}).get("summary", "In short"))
    left_title = _title_case_phrase(left_topic)
    right_title = _title_case_phrase(right_topic)
    summary_candidates = _extract_presentable_sentences(answer, context)
    summary = summary_candidates[0] if summary_candidates else "The selected material highlights the key points related to this question."
    lines = [
        f"## {left_title} vs {right_title}",
        "",
        f"| Aspect | {left_title} | {right_title} |",
        "|---|---|---|",
        *(f"| {label} | {left} | {right} |" for label, left, right in rows),
        "",
        f"> **{summary_label}:** {summary}",
    ]
    return "\n".join(lines).strip()


def generic_explain_formatter(query: str, answer: str, context: str, *, intent: str | None = None) -> str | None:
    if (intent or _detect_query_intent(query)) != "explain":
        return None

    sentences = _extract_presentable_sentences(answer, context)
    if not sentences:
        return None

    labels = _formatting_rules().get("labels") or {}
    simple_label = str(labels.get("simple_meaning", "Simple meaning"))
    key_points_label = str(labels.get("key_points", "Key points"))
    summary_label = str(labels.get("summary", "In short"))
    max_points = max(2, int(_formatting_rules().get("max_points", 4) or 4))

    title = _extract_topic_from_query(query)
    simple_meaning = sentences[0]
    bullet_points: list[str] = []
    for sentence in sentences[1:]:
        if sentence != simple_meaning and sentence not in bullet_points:
            bullet_points.append(sentence)
        if len(bullet_points) >= max_points:
            break

    if not bullet_points:
        fallback_items = _extract_list_items(answer, context)
        bullet_points = fallback_items[:max_points] or [simple_meaning]

    summary = sentences[-1] if len(sentences) > 1 else simple_meaning
    lines = [
        f"## {title}",
        "",
        f"**{simple_label}:** {simple_meaning}",
        "",
        f"### {key_points_label}",
        *(f"- {point}" for point in bullet_points[:max_points]),
        "",
        f"> **{summary_label}:** {summary}",
    ]
    return "\n".join(lines).strip()


formatter_registry: dict[str, Callable[..., str | None]] = {
    "compare": generic_compare_formatter,
    "list": generic_list_formatter,
    "explain": generic_explain_formatter,
    "definition": generic_definition_formatter,
}


def _format_answer_by_query_type(query: str, answer: str, context: str) -> str | None:
    intent = _detect_query_intent(query)
    for formatter_name in _formatting_rules().get("formatter_order", ["compare", "list", "explain", "definition"]):
        formatter = formatter_registry.get(str(formatter_name))
        if not formatter:
            continue
        formatted = formatter(query, answer, context, intent=intent)
        if formatted:
            return formatted
    return None


def _polish_short_fact_answer(answer: str, query: str, context: str = "") -> str:
    cleaned = clean_output(answer)
    if not cleaned or _is_no_info_response(cleaned) or not _is_short_fact_query(query):
        return cleaned

    text = re.sub(r"\blet['’]s find (?:out|the answer together)\b[^.?!]*[.?!]?\s*", "", cleaned, flags=re.IGNORECASE)
    text = re.sub(r"\baccording to (?:the )?(?:context|document summary|provided material|provided context|material)\b[:,]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\baccording to [`']?chunk\s*\d+[`']?(?:\s*\([^)]*\))?[:,]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bfrom the provided (?:context|material)\b[:,]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\(chapter=[^)]+\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\(topic=[^)]+\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+-\s+", ", ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,")

    sentences = _split_sentences(text)
    if not sentences:
        return cleaned

    preferred = []
    query_terms = _grounding_terms(query)
    for sentence in sentences:
        lowered = sentence.lower()
        if "according to" in lowered or "provided material" in lowered or "provided context" in lowered or "document summary" in lowered:
            continue
        preferred.append(sentence)

    if not preferred:
        preferred = sentences

    ranked = sorted(
        preferred,
        key=lambda sentence: (
            len(query_terms.intersection(_grounding_terms(sentence))),
            -len(sentence),
        ),
        reverse=True,
    )
    trimmed = ranked[0].lstrip(" ,")
    trimmed = re.sub(r"^(?:(?:so|therefore|thus)[,:\s]+)*(?:the answer is)[:,\s]+", "", trimmed, flags=re.IGNORECASE)
    trimmed = re.sub(r"^(?:so|therefore|thus)[:,\s]+", "", trimmed, flags=re.IGNORECASE)
    trimmed = trimmed[0].upper() + trimmed[1:] if trimmed else trimmed
    if not trimmed.endswith((".", "!", "?")):
        trimmed += "."
    return trimmed


def _finalize_answer_for_delivery(
    answer: str,
    query: str,
    context: str = "",
    confidence: float | None = None,
) -> tuple[str, dict[str, Any]]:
    base_cleaned = clean_output(answer)
    question_type = classify_query(query)
    if _is_short_fact_query(query) and question_type in {"fact", "definition", "quote"}:
        direct_answer = _polish_short_fact_answer(base_cleaned, query, context)
        if direct_answer:
            return direct_answer, {}

    cleaned = clean_presented_answer(base_cleaned)
    intent = _detect_query_intent(query)
    if confidence is not None and confidence < 0.45:
        return _polish_short_fact_answer(cleaned, query, context), {}

    final = strict_format_answer(query, cleaned)
    if final:
        return final, {}

    fallback_formatted = _format_answer_by_query_type(query, cleaned, context)
    if fallback_formatted:
        return fallback_formatted, {}
    return _polish_short_fact_answer(cleaned, query, context), {}


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


def _emit_context_selection_trace(
    *,
    task: str,
    selected_content_ref: str | None,
    resolved_content: dict | None,
    context_items: list[dict],
    top_k: int,
    summary_context: str,
    context: str,
) -> None:
    resolved = resolved_content or {}
    display_name = str(resolved.get("title") or "").strip()
    if not display_name:
        path = str(resolved.get("path") or "").strip()
        display_name = os.path.basename(path) if path else "general knowledge base"

    dwarn(
        "RAG",
        "Context selected for current task",
        task=str(task or "qa").strip().lower() or "qa",
        scope="selected_content" if selected_content_ref else "global_search",
        content=display_name,
        content_ref=selected_content_ref or "none",
        chunks=len(context_items),
        top_k=top_k,
        summary_loaded=bool(str(summary_context or "").strip()),
        grounded=bool(str(context or "").strip()),
    )


def _grounding_fallback_for_query(query: str, resolved_content: dict | None = None) -> str:
    if resolved_content and _is_short_fact_query(query):
        normalized = " ".join(str(query or "").strip().split())
        subject = normalized.rstrip("?.! ")
        subject = re.sub(r"^(who|what|when|where|which)\s+(is|are|was|were)\s+", "", subject, flags=re.IGNORECASE)
        subject = re.sub(r"^(define|tell me|name|list)\s+", "", subject, flags=re.IGNORECASE)
        subject = re.sub(r"^how many\s+", "", subject, flags=re.IGNORECASE)
        subject = subject.strip(" ?.!,-")
        if subject:
            return f"I couldn't find a direct answer about {subject} in the selected material."
    return _GROUNDING_FALLBACK


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

    for section in section_order:
        entries = grouped.get(section) or []
        if not entries:
            continue
        parts.append(f"{section}:")
        for item in entries:
            parts.append(f"- {str(item.get('text') or '').strip()}")

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
        "this is not clearly mentioned in the provided material",
        "this is not clearly mentioned in the selected material",
        "not found in the context",
        "not in the provided",
    )
    return any(phrase in lowered for phrase in phrases)


def _is_answer_grounded(answer: str, context: str, query: str) -> bool:
    cleaned_answer = clean_output(answer)
    if not cleaned_answer:
        dlog("RAG", "Grounding check", grounded=False, reason="empty_answer")
        return False
    if _is_no_info_response(cleaned_answer):
        dlog("RAG", "Grounding check", grounded=True, reason="explicit_no_info")
        return True
    if not str(context or "").strip():
        dlog("RAG", "Grounding check", grounded=True, reason="no_context")
        return True

    metrics = _grounding_metrics(cleaned_answer, context, query)
    short_fact = _is_short_fact_query(query)
    lowered_query = str(query or "").strip().lower()
    followup_terms = ("example", "examples", "real world", "application", "applications")
    follow_up_contextual = any(term in lowered_query for term in followup_terms) and _is_follow_up_query(query)
    query_type = classify_query(query)
    grounded = (
        (metrics["overlap_count"] >= metrics["required"] and metrics["semantic_score"] >= 0.45)
        or (metrics["overlap_count"] >= metrics["required"] and metrics["query_alignment"] >= 0.50)
        or metrics["semantic_score"] > 0.72
        or (query_type == "list" and metrics["overlap_count"] >= metrics["required"] and metrics["query_alignment"] >= 0.45)
        or (short_fact and query_type == "fact" and (metrics["overlap_count"] >= 1 and metrics["semantic_score"] >= 0.38 or metrics["query_alignment"] >= 0.50))
        or (query_type == "quote" and metrics["overlap_count"] >= 2 and metrics["semantic_score"] >= 0.35)
        or (follow_up_contextual and metrics["confidence"] >= 0.45)
    )
    dlog(
        "RAG",
        "Grounding check",
        grounded=grounded,
        overlap=f"{metrics['overlap_count']:.0f}/{metrics['required']:.0f}",
        semantic=f"{metrics['semantic_score']:.2f}",
        query_alignment=f"{metrics['query_alignment']:.2f}",
        short_fact=short_fact,
    )
    return grounded


def _build_cache_key(
    user_id: str,
    session_id: str,
    query: str,
    model_name: str,
    session_content_ref: str,
    task: str = "qa",
    user_level: str = "beginner",
) -> str:
    raw = f"{_ANSWER_FORMAT_CACHE_VERSION}:{user_id}:{session_id}:{query}:{model_name}:{session_content_ref}:{task or 'qa'}:{user_level or 'beginner'}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_policy(bypass_cache: bool = False) -> tuple[bool, str]:
    if bypass_cache:
        return False, "manual_bypass"
    if is_dev():
        return False, f"app_env={get_app_env()}"
    return True, f"app_env={get_app_env()}"


def _infer_retrieval_task(task: str, query: str) -> str:
    normalized_task = str(task or "qa").strip().lower() or "qa"
    lowered = str(query or "").strip().lower()
    query_type = classify_query(query)
    if normalized_task in {"quiz", "assessment", "summary", "lesson", "flashcards", "math", "translation"}:
        return normalized_task
    if query_type == "summary_structured" or any(term in lowered for term in ("summarize", "summarise", "summary", "overview", "key points", "main points", "gist", "short note", "revision notes", "study notes")):
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
    query_type = classify_query(query)

    if query_type == "summary_structured":
        return max(8, min(10, int(get_rag_top_k(default=4) or 4) + 4))
    if retrieval_task in {"quiz", "assessment"}:
        return 3
    if retrieval_task == "summary":
        return 5
    return configured



def _build_query_variants(query: str, task: str) -> list[str]:
    normalized_query = " ".join(str(query or "").strip().split())
    if not normalized_query:
        return []

    retrieval_task = _infer_retrieval_task(task, normalized_query)
    query_type = classify_query(normalized_query)
    intent_words = {"explain", "describe", "definition", "define", "summarize", "summarise", "summary", "overview", "quiz", "practice", "question", "questions", "revision", "note", "notes", "study"}
    keyword_tokens = [token for token in dict.fromkeys(_grounding_terms(normalized_query)) if token not in intent_words]
    if query_type == "quote":
        keyword_tokens = [token for token in keyword_tokens if token not in {"said", "say", "write", "wrote", "diary", "quote", "quoted"}]
    keyword_query = " ".join(keyword_tokens[:6]).strip()
    suffixes = {
        "qa": ["definition", "explanation"],
        "lesson": ["definition", "explanation"],
        "quiz": ["key facts", "practice questions"],
        "assessment": ["key facts", "practice questions"],
        "summary": ["summary key points", "concise overview"],
        "math": ["formula", "solved example"],
    }

    candidate_values = [normalized_query]
    if keyword_query:
        candidate_values.append(keyword_query)
        candidate_values.extend(f"{keyword_query} {suffix}" for suffix in suffixes.get(retrieval_task, []))
        if query_type == "quote":
            candidate_values.extend(
                f"{keyword_query} {suffix}" for suffix in ("exact quote", "said", "wrote", "diary line")
            )

    variants: list[str] = []
    for value in candidate_values:
        cleaned = " ".join(str(value or "").strip().split())
        if cleaned and cleaned not in variants:
            variants.append(cleaned)

    return variants[:5]



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


def _resolve_session_scope(
    user_id: str,
    session_id: str | None,
    session_content_override: Any,
) -> tuple[str, str | None, str | None, dict | None, str | None, str]:
    if not session_id:
        session_id = f"{user_id}_default"

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
        if session_content_ref is not None and not isinstance(session_content_ref, str):
            session_content_ref = None
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

    return session_id, session_content_ref, cache_content_ref, resolved_content, session_content_path, summary_context


def _build_history_text(history_data: list[dict[str, Any]]) -> str:
    return "".join(
        f"user: {item.get('question', '')}\nassistant: {item.get('answer', '')}\n"
        for item in history_data
    )


def _quote_focus_terms(query: str) -> set[str]:
    skip_terms = {"what", "did", "who", "said", "say", "write", "wrote", "quote", "quoted", "line", "diary", "his", "her", "their"}
    return {term for term in _grounding_terms(query) if term not in skip_terms}


def _prioritize_quote_context(query: str, items: list[dict]) -> list[dict]:
    focus_terms = _quote_focus_terms(query)
    if not items or not focus_terms:
        return items

    def _score(item: dict) -> tuple[int, int, float, int]:
        text = str(item.get("text") or "")
        lowered = text.lower()
        overlap = len(focus_terms.intersection(_grounding_terms(text)))
        quote_like = int(bool(re.search(r'["“”]', text)) or any(term in lowered for term in ("said", "wrote", "diary")))
        return quote_like, overlap, float(item.get("score", 0.0) or 0.0), len(text)

    return sorted(items, key=_score, reverse=True)


def _prepare_context_pipeline(
    *,
    query: str,
    normalized_task: str,
    history_data: list[dict[str, Any]],
    session_content_path: str | None,
    cache_content_ref: str | None,
    resolved_content: dict | None,
    summary_context: str,
) -> str:
    last_question = str(history_data[-1].get("question") or "").strip() if history_data else ""
    follow_up = bool(last_question) and _is_follow_up_query(query)
    enhanced_query = f"{query}. Previous question: {last_question}" if follow_up else query
    relevance_query = enhanced_query if follow_up else query

    retrieval_task = _infer_retrieval_task(normalized_task, query)
    top_k = _select_context_top_k(query, retrieval_task, summary_context=summary_context)
    context_items = _retrieve_context_items(
        enhanced_query,
        task=retrieval_task,
        filter_path=session_content_path,
        top_k=top_k,
        search_k=max(8, top_k * 2),
    )
    raw_context = "\n".join(item.get("text", "") for item in context_items).strip()
    if session_content_path and (not context_items or not is_context_relevant(relevance_query, raw_context)):
        recovered_chunks = _recover_chunks_from_selected_file(session_content_path, top_k, query=query)
        recovered_items = _context_items_from_recovered_chunks(session_content_path, recovered_chunks)
        if recovered_items:
            context_items = _dedupe_context_items(recovered_items + context_items, limit=top_k)

    if classify_query(query) == "quote":
        context_items = _prioritize_quote_context(query, context_items)

    context_items, summary_context, context_tokens = _limit_context_items_to_budget(
        context_items,
        summary_context=summary_context,
        max_tokens=MAX_CONTEXT_TOKENS,
    )
    raw_context = "\n".join(item.get("text", "") for item in context_items).strip()

    dlog(
        "RAG",
        "Context prepared",
        query=query[:120],
        follow_up=follow_up,
        chunks=len(context_items),
        context_tokens=context_tokens,
        max_tokens=MAX_CONTEXT_TOKENS,
    )
    _log_retrieved_chunks(query, context_items)
    has_relevant_context = bool(session_content_path) or is_context_relevant(relevance_query, raw_context)
    context = _format_context_block(context_items, summary_context=summary_context) if has_relevant_context and (raw_context or summary_context) else ""
    _emit_context_selection_trace(
        task=normalized_task,
        selected_content_ref=cache_content_ref,
        resolved_content=resolved_content,
        context_items=context_items,
        top_k=top_k,
        summary_context=summary_context,
        context=context,
    )
    return context


def _finalize_pipeline_answer(
    answer: str,
    query: str,
    context: str,
    resolved_content: dict | None = None,
    enforce_grounding: bool = True,
) -> tuple[str, dict[str, Any], bool]:
    cleaned = clean_output(answer)
    if not enforce_grounding:
        dlog("RAG", "Context guard relaxed grounding for weak context", query=query[:120])
        final_answer, meta = _finalize_answer_for_delivery(cleaned, query, "", confidence=None)
        return final_answer or cleaned, meta, False
    if _is_no_info_response(cleaned):
        dlog("RAG", "Fallback triggered", reason="model_no_info", query=query[:120])
        return _grounding_fallback_for_query(query, resolved_content), {}, True
    if not _is_answer_grounded(cleaned, context, query):
        metrics = _grounding_metrics(cleaned, context, query)
        dlog(
            "RAG",
            "Fallback triggered",
            reason="ungrounded_answer",
            query=query[:120],
            semantic=f"{metrics['semantic_score']:.2f}",
            confidence=f"{metrics['confidence']:.2f}",
        )
        return _grounding_fallback_for_query(query, resolved_content), {}, True

    metrics = _grounding_metrics(cleaned, context, query)
    final_answer, meta = _finalize_answer_for_delivery(cleaned, query, context, confidence=metrics["confidence"])
    return final_answer, meta, False


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
    user_level: str = "beginner",
    bypass_cache: bool = False,
) -> str:
    """Generate answer (non-streaming) with a clean retrieve→generate→validate→format pipeline."""
    t_start = time.perf_counter()
    normalized_task = str(task or "qa").strip().lower() or "qa"
    session_id, session_content_ref, cache_content_ref, resolved_content, session_content_path, summary_context = _resolve_session_scope(
        user_id,
        session_id,
        session_content_override,
    )

    use_cache, cache_reason = _cache_policy(bypass_cache)
    dlog(
        "RAG",
        "generate_answer called",
        user=user_id,
        session=session_id,
        query=query[:120],
        requested_model=model_name or "auto",
        task=normalized_task,
        user_level=user_level,
        app_env=get_app_env(),
        bypass_cache=bypass_cache,
        use_cache=use_cache,
    )

    key = None
    if use_cache:
        key = _build_cache_key(user_id, session_id, query, model_name, cache_content_ref, normalized_task, user_level)
        cached = get_cache(key)
        if cached:
            answer = str(cached.get("answer") or "")
            save_chat(
                user_id,
                session_id,
                query,
                answer,
                session_content=session_content_ref,
                selected_content=cache_content_ref,
            )
            elapsed = (time.perf_counter() - t_start) * 1000
            dlog("RAG", "Cache HIT", elapsed_ms=f"{elapsed:.1f}ms", reason=cache_reason)
            return answer
    else:
        dlog("RAG", "Cache bypassed", reason=cache_reason, query=query[:120])

    history_data = get_history(user_id, session_id)[-3:]
    context = _prepare_context_pipeline(
        query=query,
        normalized_task=normalized_task,
        history_data=history_data,
        session_content_path=session_content_path,
        cache_content_ref=cache_content_ref,
        resolved_content=resolved_content,
        summary_context=summary_context,
    )
    history_text = _build_history_text(history_data)
    query_type = classify_query(query)
    context_confidence = get_context_confidence(query, context)
    _, domain_hint = _context_domain_signal(query, _plain_context_text(context))
    normalized_query = " ".join(str(query or "").strip().lower().split())
    is_generic_confirmation = normalized_query in _GENERIC_CONFIRMATIONS

    if context_confidence < 0.30:
        use_context = False
        enforce_grounding = False
    elif query_type in {"definition", "explanation", "math"}:
        use_context = context_confidence > 0.50
        enforce_grounding = context_confidence > 0.60
    elif query_type in {"fact", "quote"}:
        use_context = context_confidence > 0.55
        enforce_grounding = use_context
    elif query_type == "list":
        use_context = context_confidence >= 0.35
        enforce_grounding = context_confidence > 0.55
    else:
        use_context = context_confidence >= 0.40
        enforce_grounding = context_confidence > 0.60

    generation_context = context if use_context else ""
    should_generate = True
    if cache_content_ref and query_type in {"fact", "quote"} and context_confidence < 0.60 and not is_generic_confirmation:
        dlog("RAG", "Selected material confidence too weak for fact/quote answer", query=query[:120], confidence=f"{context_confidence:.2f}")
        answer, answer_meta, fallback_used = _SELECTED_MATERIAL_FALLBACK, {}, True
        should_generate = False
    elif use_context and not has_strong_context_match(query, generation_context):
        if cache_content_ref:
            dlog("RAG", "No strong lexical context match for selected material", query=query[:120])
            answer, answer_meta, fallback_used = _SELECTED_MATERIAL_FALLBACK, {}, True
            should_generate = False
        else:
            dlog("RAG", "No strong lexical context match; switching to general tutor mode", query=query[:120])
            use_context = False
            enforce_grounding = False
            generation_context = ""

    generation_query = _apply_user_level_guidance(
        query,
        user_level,
        allow_general_knowledge=not use_context,
        domain_hint=domain_hint if use_context else "",
    )

    dlog(
        "RAG",
        "Answering mode selected",
        query=query[:120],
        query_type=query_type,
        context_confidence=f"{context_confidence:.2f}",
        use_context=use_context,
        enforce_grounding=enforce_grounding,
    )

    if not use_context and is_generic_confirmation:
        answer, answer_meta, fallback_used = _grounding_fallback_for_query(query, resolved_content), {}, True
    elif not should_generate:
        pass
    else:
        raw_answer = generate_response(
            context=generation_context,
            query=generation_query,
            history=history_text,
            model_name=model_name,
            task=normalized_task,
        )
        answer, answer_meta, fallback_used = _finalize_pipeline_answer(
            raw_answer,
            query,
            generation_context,
            resolved_content,
            enforce_grounding=enforce_grounding,
        )

    if use_cache and key:
        set_cache(key, {"answer": answer, "meta": answer_meta})
        dlog("RAG", "Cache write complete", reason=cache_reason)
    else:
        dlog("RAG", "Cache write skipped", reason=cache_reason)
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
    user_level: str = "beginner",
    bypass_cache: bool = False,
):
    """Stream answer token-by-token using the same clean pipeline as non-streaming answers."""
    t_start = time.perf_counter()
    normalized_task = str(task or "qa").strip().lower() or "qa"
    use_cache, cache_reason = _cache_policy(bypass_cache)
    dlog(
        "RAG",
        "generate_answer_stream called",
        user=user_id,
        session=session_id or f"{user_id}_default",
        query=str(query)[:120],
        requested_model=model_name or "auto",
        task=normalized_task,
        user_level=user_level,
        app_env=get_app_env(),
        bypass_cache=bypass_cache,
        use_cache=use_cache,
    )
    session_id, session_content_ref, cache_content_ref, resolved_content, session_content_path, summary_context = _resolve_session_scope(
        user_id,
        session_id,
        session_content_override,
    )

    key = None
    if use_cache:
        key = _build_cache_key(user_id, session_id, query, model_name, cache_content_ref, normalized_task, user_level)
        cached = get_cache(key)
        if cached:
            meta = dict(cached.get("meta") or {})
            answer = str(cached.get("answer") or "")
            save_chat(
                user_id,
                session_id,
                query,
                answer,
                session_content=session_content_ref,
                selected_content=cache_content_ref,
            )
            dlog("RAG", "Stream cache HIT", reason=cache_reason)
            yield {"text": answer, "replaceText": True, **meta}
            return
    else:
        dlog("RAG", "Stream cache bypassed", reason=cache_reason, query=str(query)[:120])

    history_data = get_history(user_id, session_id)[-3:]

    save_chat(
        user_id,
        session_id,
        query,
        "",
        session_content=session_content_ref,
        selected_content=cache_content_ref,
    )

    context = _prepare_context_pipeline(
        query=query,
        normalized_task=normalized_task,
        history_data=history_data,
        session_content_path=session_content_path,
        cache_content_ref=cache_content_ref,
        resolved_content=resolved_content,
        summary_context=summary_context,
    )
    history_text = _build_history_text(history_data)
    query_type = classify_query(query)
    context_confidence = get_context_confidence(query, context)
    _, domain_hint = _context_domain_signal(query, _plain_context_text(context))
    normalized_query = " ".join(str(query or "").strip().lower().split())
    is_generic_confirmation = normalized_query in _GENERIC_CONFIRMATIONS

    if context_confidence < 0.30:
        use_context = False
        enforce_grounding = False
    elif query_type in {"definition", "explanation", "math"}:
        use_context = context_confidence > 0.50
        enforce_grounding = context_confidence > 0.60
    elif query_type in {"fact", "quote"}:
        use_context = context_confidence > 0.55
        enforce_grounding = use_context
    elif query_type == "list":
        use_context = context_confidence >= 0.35
        enforce_grounding = context_confidence > 0.55
    else:
        use_context = context_confidence >= 0.40
        enforce_grounding = context_confidence > 0.60

    generation_context = context if use_context else ""
    should_generate = True
    if cache_content_ref and query_type in {"fact", "quote"} and context_confidence < 0.60 and not is_generic_confirmation:
        dlog("RAG", "Selected material confidence too weak for fact/quote stream answer", query=str(query)[:120], confidence=f"{context_confidence:.2f}")
        full_response = _SELECTED_MATERIAL_FALLBACK
        should_generate = False
    elif use_context and not has_strong_context_match(query, generation_context):
        if cache_content_ref:
            dlog("RAG", "No strong lexical context match for selected material (stream)", query=str(query)[:120])
            full_response = _SELECTED_MATERIAL_FALLBACK
            should_generate = False
        else:
            dlog("RAG", "No strong lexical context match; streaming in general tutor mode", query=str(query)[:120])
            use_context = False
            enforce_grounding = False
            generation_context = ""

    generation_query = _apply_user_level_guidance(
        query,
        user_level,
        allow_general_knowledge=not use_context,
        domain_hint=domain_hint if use_context else "",
    )

    response_meta: dict[str, Any] = {}
    dlog(
        "RAG",
        "Streaming answering mode selected",
        query=str(query)[:120],
        query_type=query_type,
        context_confidence=f"{context_confidence:.2f}",
        use_context=use_context,
        enforce_grounding=enforce_grounding,
    )

    if not use_context and is_generic_confirmation:
        full_response = _grounding_fallback_for_query(query, resolved_content)
        yield full_response
    elif not should_generate:
        yield full_response
    else:
        full_response = ""
        for token in generate_response_stream(generation_context, generation_query, history_text, model_name, task=normalized_task):
            yield token
            full_response += token
        full_response, response_meta, _ = _finalize_pipeline_answer(
            full_response,
            query,
            generation_context,
            resolved_content,
            enforce_grounding=enforce_grounding,
        )

    yield {"text": full_response, "replaceText": True, **response_meta}
    if use_cache and key:
        set_cache(key, {"answer": full_response, "meta": response_meta})
        dlog("RAG", "Stream cache write complete", reason=cache_reason)
    else:
        dlog("RAG", "Stream cache write skipped", reason=cache_reason)
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
def _recover_chunks_from_selected_file(filter_path: str | None, top_k: int, query: str = "") -> list[str]:
    candidate = str(filter_path or "").strip()
    if not candidate or not os.path.isfile(candidate):
        return []

    try:
        extracted_text = extract_text_from_pdf(candidate)
    except Exception as exc:
        dlog("RAG", "Selected file extraction fallback failed", path=candidate, error=str(exc))
        extracted_text = ""

    try:
        ocr_text = extract_ocr_text_from_pdf(candidate, query=query)
    except Exception as exc:
        dlog("RAG", "Selected file OCR fallback failed", path=candidate, error=str(exc))
        ocr_text = ""

    candidate_chunks: list[str] = []
    if extracted_text:
        candidate_chunks.extend(chunk for chunk in chunk_text(extracted_text) if str(chunk or "").strip())
    if ocr_text:
        ocr_chunks = chunk_text(f"Extracted visual text:\n{ocr_text}", chunk_size=600, overlap=80)
        candidate_chunks.extend(chunk for chunk in ocr_chunks if str(chunk or "").strip())

    if candidate_chunks:
        ranking_query = str(query or os.path.splitext(os.path.basename(candidate))[0]).strip() or os.path.basename(candidate)
        ranked = rank_chunks(ranking_query, candidate_chunks)
        deduped: list[str] = []
        seen: set[str] = set()
        for chunk in ranked:
            key = re.sub(r"\s+", " ", str(chunk or "")).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(str(chunk).strip())
            if len(deduped) >= top_k:
                break
        if deduped:
            return deduped

    summary_text = str(get_summary(candidate) or "").strip()
    if summary_text:
        return [summary_text]
    return []


def _context_items_from_recovered_chunks(source_path: str, recovered_chunks: list[str]) -> list[dict]:
    chapter_name = os.path.splitext(os.path.basename(source_path))[0]
    items: list[dict] = []
    for chunk in recovered_chunks[:]:
        text = str(chunk or "").strip()
        if not text:
            continue
        lowered = text.lower()
        modality = "ocr" if any(marker in lowered for marker in ("diagram labels", "extracted visual text", "page ")) else "text"
        items.append(
            {
                "text": text,
                "source": source_path,
                "metadata": {
                    "type": "concept",
                    "chapter": chapter_name,
                    "topic": chapter_name,
                    "modality": modality,
                    "is_diagram_label": modality == "ocr",
                },
                "score": 0.0,
                "index_name": "concept_index",
            }
        )
    return items


def retrieve_chunks(chapter: str, top_k: int = 5, filter_path: str | None = None):
    """Retrieve lesson chunks using the same generic retrieval + recovery flow as the main RAG pipeline."""
    query = (chapter or "").strip()
    if not query:
        return []

    items = _retrieve_context_items(
        query,
        task="lesson",
        filter_path=filter_path,
        top_k=top_k,
        search_k=max(8, top_k * 2),
    )
    selected_chunks = [str(item.get("text") or "").strip() for item in items if str(item.get("text") or "").strip()]
    if selected_chunks:
        dwarn(
            "RAG",
            "Lesson retrieval context selected",
            task="lesson",
            scope="selected_file_semantic" if filter_path else "semantic_search",
            chapter=query[:100],
            content=os.path.basename(str(filter_path or "")).strip() or "knowledge base",
            chunks=len(selected_chunks),
            top_k=top_k,
        )
        return selected_chunks

    recovered_chunks = _recover_chunks_from_selected_file(filter_path, top_k, query=query) if filter_path else []
    dwarn(
        "RAG",
        "Lesson retrieval context selected",
        task="lesson",
        scope="selected_file_recovery" if recovered_chunks and filter_path else ("selected_file_semantic" if filter_path else "semantic_search"),
        chapter=query[:100],
        content=os.path.basename(str(filter_path or "")).strip() or "knowledge base",
        chunks=len(recovered_chunks or []),
        top_k=top_k,
    )
    return recovered_chunks
