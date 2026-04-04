"""Compatibility-first generator execution for Step 9.

This module routes quiz, flashcard, and summary requests to the existing
specialized generation flows while preserving the current `/ask` and `/ws/ask`
contracts.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from .faiss_store import search
from .file_management import resolve_content_reference
from .flashcards import FlashcardItem, _save_flashcards_artifact, generate_flashcards_from_text
from .ingestion import get_summary
from .model_manager import generate_response
from .quiz import generate_quiz


_GENERATOR_TASKS = {"quiz", "flashcards", "summary"}


def is_generator_task(task: Optional[str]) -> bool:
    return str(task or "").strip().lower() in _GENERATOR_TASKS


def _topic_from_query(query: str, fallback: str = "this topic") -> str:
    text = str(query or "").strip()
    if not text:
        return fallback

    patterns = [
        r"(?:quiz|flashcards|summary|summarize|summarise)\s+(?:for|on|about)\s+(.+)",
        r"(?:create|make|generate)\s+(?:a\s+)?(?:quiz|summary|flashcards)\s+(?:for|on|about)\s+(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip(" .?!")
            if cleaned:
                return cleaned

    return text[:80].strip(" .?!") or fallback


def _resolve_selected_content(user_id: str, content_id: Optional[str]) -> Optional[dict]:
    if not content_id:
        return None
    try:
        return resolve_content_reference({"username": user_id}, content_id)
    except Exception:
        return None


def _build_context_text(query: str, *, task: str, content_id: Optional[str], user_id: str) -> tuple[str, Optional[dict]]:
    resolved = _resolve_selected_content(user_id, content_id)
    summary_text = ""
    if resolved and resolved.get("path"):
        try:
            summary_text = (get_summary(resolved["path"]) or "").strip()
        except Exception:
            summary_text = ""

    search_results = search(
        query,
        filter_path=resolved.get("path") if resolved else None,
        top_k=6,
        search_k=12,
        task=task,
    )
    pieces = []
    if summary_text:
        pieces.append(f"Document summary:\n{summary_text}")
    if search_results:
        pieces.append("\n".join(search_results[:6]))
    if not pieces:
        pieces.append(query)
    return "\n\n".join(part for part in pieces if part).strip(), resolved


def _format_quiz_text(topic: str, payload: dict) -> str:
    questions = payload.get("questions") or []
    lines = [f"Quiz: {topic}"]
    for index, item in enumerate(questions[:5], start=1):
        lines.append(f"{index}. {item.get('question', f'Question {index}')}")
        options = item.get("options") or []
        for opt_index, option in enumerate(options[:4]):
            label = chr(ord("A") + opt_index)
            lines.append(f"   {label}. {option}")
    return "\n".join(lines).strip()


def _format_flashcards_text(topic: str, cards: list[FlashcardItem]) -> str:
    lines = [f"Flashcards: {topic}"]
    for index, card in enumerate(cards[:8], start=1):
        lines.append(f"Q{index}: {card.question}")
        lines.append(f"A{index}: {card.answer}")
    return "\n".join(lines).strip()


def _format_summary_text(topic: str, summary: str) -> str:
    cleaned = str(summary or "").strip()
    if not cleaned:
        cleaned = "No summary could be generated from the available study material."
    return f"Summary: {topic}\n{cleaned}".strip()


def execute_generator_task(
    *,
    task: str,
    query: str,
    user_id: str,
    session_id: str,
    model_name: Optional[str] = None,
    content_id: Optional[str] = None,
) -> str:
    normalized_task = str(task or "").strip().lower()
    if normalized_task not in _GENERATOR_TASKS:
        raise ValueError(f"Unsupported generator task: {task}")

    context_text, resolved = _build_context_text(
        query,
        task=normalized_task,
        content_id=content_id,
        user_id=user_id,
    )
    topic = _topic_from_query(query, fallback=(resolved or {}).get("title") or "study material")

    if normalized_task == "quiz":
        payload = generate_quiz(
            user_id=user_id,
            session_id=session_id,
            chapter=topic,
            model_name=model_name,
            context_hint=query,
        )
        return _format_quiz_text(topic, payload)

    if normalized_task == "flashcards":
        cards = generate_flashcards_from_text(context_text, num_cards=8)
        if not cards:
            cards = [FlashcardItem(question=f"What is important about {topic}?", answer="Review the key ideas and examples from the study material.")]
        if session_id:
            title = f"Flashcards - {topic}"
            selected_content = content_id or ((resolved or {}).get("path") if resolved else None)
            try:
                _save_flashcards_artifact(user_id, session_id, title, cards, selected_content=selected_content)
            except Exception:
                pass
        return _format_flashcards_text(topic, cards)

    cached_summary = ""
    if resolved and resolved.get("path"):
        try:
            cached_summary = (get_summary(resolved["path"]) or "").strip()
        except Exception:
            cached_summary = ""

    if cached_summary:
        return _format_summary_text(topic, cached_summary)

    prompt = (
        "Create a concise study summary from the provided context. "
        "Use short student-friendly bullet points when helpful and keep it factual."
    )
    summary = generate_response(context=context_text, query=prompt, model_name=model_name, task="summary")
    if not str(summary or "").strip() and context_text:
        snippet = context_text.replace("\n", " ").strip()
        summary = snippet[:500]
    return _format_summary_text(topic, summary)
