"""Card-level learning artifact generation and persistence."""

import json
from datetime import datetime, UTC
from typing import Dict, List, Optional

from .db import get_connection
from .model_manager import generate_response
from .quiz import _extract_quiz_json, _normalize_questions


def _save_artifact(
    user_id: str,
    session_id: Optional[str],
    lesson_plan_id: Optional[int],
    card_id: int,
    artifact_type: str,
    payload: Dict,
    title: Optional[str] = None,
    selected_content: Optional[str] = None,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO learning_artifacts
        (user_id, session_id, lesson_plan_id, card_id, artifact_type, title, payload_json, selected_content, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (user_id, session_id, lesson_plan_id, card_id, artifact_type, title, json.dumps(payload), selected_content),
    )
    artifact_id = int(cursor.lastrowid)
    conn.commit()
    conn.close()
    return artifact_id


def _build_card_context_text(card: Dict) -> str:
    sections: List[str] = []

    content = str(card.get("content") or "").strip()
    if content:
        sections.append(content)

    bullets = [str(item).strip() for item in (card.get("bullets") or []) if str(item).strip()]
    if bullets:
        sections.append("Key points:\n" + "\n".join(f"- {item}" for item in bullets[:6]))

    numbered = [str(item).strip() for item in (card.get("numbered") or []) if str(item).strip()]
    if numbered:
        sections.append("Ordered prompts:\n" + "\n".join(f"{idx}. {item}" for idx, item in enumerate(numbered[:6], start=1)))

    if not sections:
        sections.append(str(card.get("title") or "Lesson card").strip() or "Lesson card")

    return "\n\n".join(sections)


def generate_card_quiz(
    user_id: str,
    card: Dict,
    num_questions: int = 5,
    context_hint: Optional[str] = None,
    selected_content: Optional[str] = None,
) -> Dict:
    context = _build_card_context_text(card)
    prompt = f"""
Create {num_questions} multiple-choice quiz questions using ONLY the lesson card context.
Return ONLY valid JSON:
{{
  "questions": [
    {{"id":"q1", "question":"...", "options":["...","...","...","..."], "correct_answer":"A", "explanation":"..."}}
  ]
}}
RULES:
- Every question must be answerable from the lesson card only.
- Always include exactly 4 options.
- Always include correct_answer and explanation.
- Do not add commentary outside the JSON.

Preferred quiz focus (optional):
{(context_hint or '').strip() or 'No special focus provided.'}

Lesson card title:
{card.get('title', 'Lesson card')}

Lesson card context:
{context}
"""

    try:
        raw = generate_response(context=context, query=prompt, task="quiz")
        parsed = _extract_quiz_json(raw)
    except Exception:
        parsed = {"questions": []}

    questions = _normalize_questions(
        parsed.get("questions", []),
        num_questions=num_questions,
        fallback_context=context,
        chapter=str(card.get("title") or "Lesson card"),
    )

    payload = {
        "quiz": questions,
        "generated_at": datetime.now(UTC).isoformat(),
        "selected_content": selected_content,
        "context_source": "lesson_card",
    }
    artifact_id = _save_artifact(
        user_id=user_id,
        session_id=card.get("session_id"),
        lesson_plan_id=card.get("lesson_plan_id"),
        card_id=card["card_id"],
        artifact_type="QUIZ",
        payload=payload,
        title=f"Quiz - {card.get('title', 'Card')}",
        selected_content=selected_content,
    )
    return {"artifact_id": artifact_id, "payload": payload}


def generate_card_flashcards(
        user_id: str,
        card: Dict,
        num_cards: int = 8,
        context_hint: Optional[str] = None,
        selected_content: Optional[str] = None,
) -> Dict:
    context = card.get("content") or card.get("title")
    prompt = f"""
Generate {num_cards} concise study flashcards from the card context.
Return strict JSON:
{{
  "flashcards": [
    {{"question":"...", "answer":"..."}}
  ]
}}
Preferred flashcard focus (optional):
{(context_hint or '').strip() or 'No special focus provided.'}

Card context:
{context}
"""

    cards: List[Dict[str, str]] = []
    try:
        raw = generate_response(context=context, query=prompt, task="flashcards")
        parsed = json.loads(raw)
        for item in parsed.get("flashcards", [])[:num_cards]:
            cards.append(
                {
                    "question": item.get("question", ""),
                    "answer": item.get("answer", ""),
                }
            )
    except Exception:
        cards = []

    while len(cards) < num_cards:
        idx = len(cards) + 1
        cards.append(
            {
                "question": f"Key point {idx} from {card.get('title', 'this card')}?",
                "answer": "Review the concept summary and examples for this card.",
            }
        )

    payload = {"flashcards": cards, "generated_at": datetime.now(UTC).isoformat()}
    artifact_id = _save_artifact(
        user_id=user_id,
        session_id=card.get("session_id"),
        lesson_plan_id=card.get("lesson_plan_id"),
        card_id=card["card_id"],
        artifact_type="FLASHCARD",
        payload=payload,
        title=f"Flashcards - {card.get('title', 'Card')}",
        selected_content=selected_content,
    )
    return {"artifact_id": artifact_id, "payload": payload}


def get_artifact(user_id: str, artifact_id: int) -> Optional[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, user_id, session_id, lesson_plan_id, card_id, artifact_type, title, tags, payload_json, created_at, updated_at
        FROM learning_artifacts
        WHERE id=? AND user_id=?
        LIMIT 1
        """,
        (artifact_id, user_id),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    payload = {}
    try:
        payload = json.loads(row[8] or "{}")
    except Exception:
        payload = {}

    return {
        "artifact_id": int(row[0]),
        "user_id": row[1],
        "session_id": row[2],
        "lesson_plan_id": row[3],
        "card_id": row[4],
        "artifact_type": row[5],
        "title": row[6],
        "tags": row[7],
        "payload": payload,
        "created_at": row[9],
        "updated_at": row[10],
    }


def list_flashcard_sessions(user_id: str) -> List[Dict]:
    """Return flashcard sessions ordered by most recent artifact activity."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            la.session_id,
            MAX(COALESCE(la.updated_at, la.created_at)) AS last_updated,
            MAX(la.id) AS latest_artifact_id,
            (
                SELECT la2.payload_json
                FROM learning_artifacts la2
                WHERE la2.user_id=? AND la2.session_id=la.session_id AND la2.artifact_type='FLASHCARD'
                ORDER BY la2.id DESC
                LIMIT 1
            ) AS latest_payload_json,
            (
                SELECT lp.chapter
                FROM lesson_plans lp
                WHERE lp.user_id=? AND lp.session_id=la.session_id
                ORDER BY lp.id DESC
                LIMIT 1
            ) AS chapter,
            (
                SELECT la2.selected_content
                FROM learning_artifacts la2
                WHERE la2.user_id=? AND la2.session_id=la.session_id AND la2.artifact_type='FLASHCARD'
                ORDER BY la2.id DESC
                LIMIT 1
            ) AS selected_content
        FROM learning_artifacts la
        WHERE la.user_id=? AND la.artifact_type='FLASHCARD' AND la.session_id IS NOT NULL AND la.session_id != ''
        GROUP BY la.session_id
        ORDER BY MAX(COALESCE(la.updated_at, la.created_at)) DESC, MAX(la.id) DESC
        """,
        (user_id, user_id, user_id, user_id),
    )
    rows = cursor.fetchall()
    conn.close()

    sessions = []
    for row in rows:
        session_id = row[0]
        if not session_id:
            continue

        custom_title = None
        try:
            payload = json.loads(row[3] or "{}")
            maybe_title = payload.get("session_title")
            if isinstance(maybe_title, str) and maybe_title.strip():
                custom_title = maybe_title.strip()
        except Exception:
            custom_title = None

        chapter = row[4]
        selected_content = row[5]
        sessions.append(
            {
                "id": session_id,
                "title": custom_title or (f"Cards - {chapter}" if chapter else "Cards Session"),
                "chapter": chapter,
                "last_updated": row[1],
                "latest_artifact_id": int(row[2]) if row[2] is not None else None,
                "selected_content": selected_content,
            }
        )

    return sessions


def get_latest_flashcard_artifact_for_session(user_id: str, session_id: str) -> Optional[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id
        FROM learning_artifacts
        WHERE user_id=? AND session_id=? AND artifact_type='FLASHCARD'
        ORDER BY COALESCE(updated_at, created_at) DESC, id DESC
        LIMIT 1
        """,
        (user_id, session_id),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return get_artifact(user_id, int(row[0]))


def rename_flashcard_session(user_id: str, session_id: str, title: str) -> Dict:
    """Persist a custom title for all flashcard artifacts in a session."""
    cleaned_title = (title or "").strip()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, payload_json
        FROM learning_artifacts
        WHERE user_id=? AND session_id=? AND artifact_type='FLASHCARD'
        """,
        (user_id, session_id),
    )
    rows = cursor.fetchall()
    if not rows:
        conn.close()
        return {"status": "not_found"}

    for row in rows:
        payload = {}
        try:
            payload = json.loads(row[1] or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}

        payload["session_title"] = cleaned_title
        cursor.execute(
            """
            UPDATE learning_artifacts
            SET payload_json=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (json.dumps(payload), int(row[0])),
        )

    conn.commit()
    conn.close()
    return {"status": "updated"}


def delete_flashcard_session(user_id: str, session_id: str) -> Dict:
    """Delete flashcard artifacts for a session without removing lesson plans."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM learning_artifacts
        WHERE user_id=? AND session_id=? AND artifact_type='FLASHCARD'
        """,
        (user_id, session_id),
    )
    deleted_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return {"status": "deleted", "deleted_artifacts": deleted_rows}


def update_artifact_meta(user_id: str, artifact_id: int, title: Optional[str], tags: Optional[List[str]]) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE learning_artifacts
        SET title=COALESCE(?, title),
            tags=COALESCE(?, tags),
            updated_at=CURRENT_TIMESTAMP
        WHERE id=? AND user_id=?
        """,
        (title, json.dumps(tags) if tags is not None else None, artifact_id, user_id),
    )
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated
