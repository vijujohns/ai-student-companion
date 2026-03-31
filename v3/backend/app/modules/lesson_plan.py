"""
lesson_plan.py

Smart Lesson Plan System for Brain Teaser
--------------------------------------------
Handles:
- LLM-generated lesson plan creation per chapter
- Persistent storage and retrieval of lesson plans
- Step-by-step progress tracking
- Revision and quiz integration
"""

import json
import re
import uuid
from datetime import datetime, UTC
from typing import List, Dict, Optional
from .db import get_connection
from .rag import retrieve_chunks
from .model_manager import generate_response
from .quiz import generate_quiz, get_quiz, submit_quiz_answer


# -------------------------
# Helper: Default Step Template
# -------------------------
def default_steps() -> List[Dict]:
    """Return generic lesson steps with no content (used only as last resort)."""
    return [
        {"id": 1, "title": "Introduction", "type": "concept", "status": "pending", "content": ""},
        {"id": 2, "title": "Key Concepts", "type": "concept", "status": "pending", "content": ""},
        {"id": 3, "title": "Examples / Case Study", "type": "example", "status": "pending", "content": ""},
        {"id": 4, "title": "Quiz", "type": "quiz", "status": "pending", "content": ""},
        {"id": 5, "title": "Revision", "type": "revision", "status": "pending", "content": ""},
    ]


def _extract_json_from_text(text: str) -> Optional[Dict]:
    """Try multiple strategies to extract JSON from LLM free-text output."""
    if not text:
        return None
    # 1. Direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # 2. Fenced JSON block
    for pattern in [r'```json\s*([\s\S]+?)\s*```', r'```\s*(\{[\s\S]+?\})\s*```']:
        m = re.search(pattern, text)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
    # 3. First {...} block
    m = re.search(r'(\{[\s\S]+\})', text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None


def _steps_from_llm_text(text: str, chunks: List[str]) -> List[Dict]:
    """
    Parse numbered/headed sections from LLM free-text into step dicts.
    Returns empty list if fewer than 2 sections found.
    """
    section_re = re.compile(
        r'(?:^|\n)(?:(?:\d+[\.:\)]\s*)|(?:#{1,3}\s*)|(?:Step\s+\d+[:\.\-]\s*))(.+?)(?=\n|$)',
        re.MULTILINE,
    )
    titles = [m.group(1).strip() for m in section_re.finditer(text) if m.group(1).strip()]
    # Also look for lines that are ALL-CAPS or Title Case short phrases
    if len(titles) < 2:
        return []

    total_chunks = len(chunks)
    steps = []
    for idx, title in enumerate(titles[:8], start=1):
        start = ((idx - 1) * total_chunks) // min(len(titles), 8)
        end = (idx * total_chunks) // min(len(titles), 8)
        content_chunks = chunks[start:end]
        content = " ".join(content_chunks)[:600].strip() if content_chunks else ""
        steps.append({
            "id": idx,
            "title": title[:120],
            "type": "concept",
            "status": "pending",
            "content": content,
        })
    return steps


def _default_steps_with_content(chunks: List[str], chapter: str) -> List[Dict]:
    """
    Build the standard 5-step outline but populate each card with actual
    chapter text from the retrieved RAG chunks.
    """
    titles = [
        ("Introduction", "concept"),
        ("Key Concepts", "concept"),
        ("Examples & Applications", "example"),
        ("Practice Questions", "quiz"),
        ("Summary & Revision", "revision"),
    ]
    total = len(chunks)
    steps = []
    for idx, (title, stype) in enumerate(titles, start=1):
        start = ((idx - 1) * total) // len(titles)
        end = (idx * total) // len(titles)
        content_chunks = chunks[start:end]
        if content_chunks:
            content = " ".join(content_chunks)[:600].strip()
        else:
            content = f"Refer to your {chapter} notes for this section."
        steps.append({
            "id": idx,
            "title": title,
            "type": stype,
            "status": "pending",
            "content": content,
        })
    return steps


def _normalize_steps(steps: List[Dict]) -> List[Dict]:
    normalized = []
    for idx, step in enumerate(steps, start=1):
        normalized.append(
            {
                "id": int(step.get("id", idx)),
                "title": str(step.get("title", f"Step {idx}")),
                "type": str(step.get("type", "concept")),
                "status": str(step.get("status", "pending")),
                "content": str(step.get("content", "")),
            }
        )
    return normalized


def _save_lesson_cards(cursor, lesson_plan_id: int, steps: List[Dict]):
    cursor.execute("DELETE FROM lesson_cards WHERE lesson_plan_id=?", (lesson_plan_id,))
    for order, step in enumerate(steps, start=1):
        content_json = json.dumps(
            {
                "status": step.get("status", "pending"),
                "content": step.get("content", ""),
            }
        )
        cursor.execute(
            """
            INSERT INTO lesson_cards (lesson_plan_id, card_order, title, card_type, content_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (lesson_plan_id, order, step.get("title", f"Step {order}"), step.get("type", "concept"), content_json),
        )


# -------------------------
# Generate Smart Lesson Plan
# -------------------------
def generate_lesson_plan(
    user_id: str,
    session_id: Optional[str],
    chapter: str,
    model_name: Optional[str] = None,
    lesson_context: Optional[str] = None,
) -> Dict:
    """
    Generate a structured lesson plan for a chapter.
    Uses RAG to retrieve chapter content and optionally LLM for smart steps.
    Saves the plan to the database.

    Args:
        user_id: Student ID
        session_id: Current session ID
        chapter: Chapter name
        model_name: Optional model to generate lesson plan
        lesson_context: Optional user preference for lesson style/focus

    Returns:
        Dict: Structured lesson plan
    """

    if not session_id:
        session_id = str(uuid.uuid4())

    # 🔹 Retrieve chapter content (RAG)
    chunks = retrieve_chunks(chapter)
    context = " ".join(chunks[:10])  # limit for initial prompt

    context_hint = (lesson_context or "").strip()

    # 🔹 Build prompt for LLM
    prompt = f"""
You are an AI tutor. Generate a detailed lesson plan for the chapter below.
Constraints:
- Use only the provided content.
- Divide content into clear subtopics.
- Suggest exercises, examples, and context-aware quizzes.
- Include revision steps for weak areas.
- Return valid JSON only (no markdown, no commentary).
- JSON must be an object with a top-level key "steps".
- Each step must include: title, type, content.
- Allowed step types: concept, example, quiz, revision.

Preferred Lesson Focus (optional):
{context_hint or "No special focus provided."}

Chapter Content:
{context}

Required Output Format:
{{
    "steps": [
        {{"title": "Introduction", "type": "concept", "content": "..."}},
        {{"title": "Key Concepts", "type": "concept", "content": "..."}},
        {{"title": "Examples", "type": "example", "content": "..."}},
        {{"title": "Practice Quiz", "type": "quiz", "content": "..."}},
        {{"title": "Revision", "type": "revision", "content": "..."}}
    ]
}}
"""

    try:
        if model_name:
            plan_text = generate_response(context=context, query=prompt, model_name=model_name, task="qa")
        else:
            plan_text = generate_response(context=context, query=prompt, task="qa")
    except Exception:
        # Fallback to default steps if LLM fails
        plan_text = None

    # 🔹 Parse LLM output; keep chapter grounding on every fallback path
    steps = []
    plan_json = _extract_json_from_text(plan_text or "")
    if isinstance(plan_json, dict):
        maybe_steps = plan_json.get("steps")
        if isinstance(maybe_steps, list):
            steps = maybe_steps

    # If model returned plain text, salvage structure from headings.
    if not steps and plan_text:
        steps = _steps_from_llm_text(plan_text, chunks)

    # Last fallback: build standard steps but fill with retrieved chapter content.
    if not steps:
        steps = _default_steps_with_content(chunks, chapter) if chunks else default_steps()

    steps = _normalize_steps(steps)

    # 🔹 Construct final lesson plan
    plan = {
        "session_id": session_id,
        "chapter": chapter,
        "steps": steps
    }

    # 🔹 Save plan to DB
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO lesson_plans (user_id, session_id, chapter, plan_json)
        VALUES (?, ?, ?, ?)
    """, (user_id, session_id, chapter, json.dumps(plan)))
    lesson_plan_id = int(cursor.lastrowid)
    _save_lesson_cards(cursor, lesson_plan_id, steps)
    conn.commit()
    conn.close()

    plan["lesson_plan_id"] = lesson_plan_id

    return plan


def list_lesson_sessions(user_id: str) -> List[Dict]:
    """Return saved lesson sessions ordered by most recent activity."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            session_id,
            chapter,
            plan_json,
            created_at
        FROM lesson_plans
        WHERE user_id=?
        ORDER BY created_at DESC, id DESC
        """,
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    sessions: List[Dict] = []
    seen_sessions = set()
    for row in rows:
        session_id = row[0]
        if not session_id or session_id in seen_sessions:
            continue

        chapter = row[1]
        plan_json = row[2]
        last_updated = row[3]

        custom_title = None
        try:
            payload = json.loads(plan_json or "{}")
            maybe_title = payload.get("session_title")
            if isinstance(maybe_title, str) and maybe_title.strip():
                custom_title = maybe_title.strip()
        except Exception:
            custom_title = None

        sessions.append(
            {
                "id": session_id,
                "title": custom_title or (f"Lesson - {chapter}" if chapter else "Lesson Session"),
                "chapter": chapter,
                "last_updated": last_updated,
            }
        )
        seen_sessions.add(session_id)

    return sessions


def rename_lesson_session(user_id: str, session_id: str, title: str) -> Dict:
    """Persist a custom title for all plans under a lesson session."""
    cleaned_title = (title or "").strip()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, plan_json
        FROM lesson_plans
        WHERE user_id=? AND session_id=?
        """,
        (user_id, session_id),
    )
    rows = cursor.fetchall()
    if not rows:
        conn.close()
        return {"status": "not_found"}

    for row in rows:
        plan_id = int(row[0])
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
            UPDATE lesson_plans
            SET plan_json=?
            WHERE id=?
            """,
            (json.dumps(payload), plan_id),
        )

    conn.commit()
    conn.close()
    return {"status": "updated"}


def delete_lesson_session(user_id: str, session_id: str) -> Dict:
    """Delete all lesson resources tied to a lesson session."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id
        FROM lesson_plans
        WHERE user_id=? AND session_id=?
        """,
        (user_id, session_id),
    )
    lesson_plan_ids = [int(row[0]) for row in cursor.fetchall()]

    if lesson_plan_ids:
        placeholders = ",".join(["?"] * len(lesson_plan_ids))
        cursor.execute(
            f"""
            DELETE FROM lesson_card_progress
            WHERE user_id=? AND lesson_plan_id IN ({placeholders})
            """,
            (user_id, *lesson_plan_ids),
        )
        cursor.execute(
            f"""
            DELETE FROM learning_artifacts
            WHERE user_id=? AND (session_id=? OR lesson_plan_id IN ({placeholders}))
            """,
            (user_id, session_id, *lesson_plan_ids),
        )
        cursor.execute(
            f"""
            DELETE FROM lesson_cards
            WHERE lesson_plan_id IN ({placeholders})
            """,
            (*lesson_plan_ids,),
        )

    cursor.execute(
        """
        DELETE FROM lesson_progress
        WHERE user_id=? AND session_id=?
        """,
        (user_id, session_id),
    )
    cursor.execute(
        """
        DELETE FROM lesson_quizzes
        WHERE user_id=? AND session_id=?
        """,
        (user_id, session_id),
    )
    cursor.execute(
        """
        DELETE FROM lesson_quiz_results
        WHERE user_id=? AND session_id=?
        """,
        (user_id, session_id),
    )
    cursor.execute(
        """
        DELETE FROM lesson_plans
        WHERE user_id=? AND session_id=?
        """,
        (user_id, session_id),
    )

    deleted_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return {"status": "deleted", "deleted_plans": deleted_rows}


# -------------------------
# Get Existing Lesson Plan
# -------------------------
def get_lesson_plan(user_id: str, session_id: str) -> Optional[Dict]:
    """
    Retrieve the most recent lesson plan for a user session.

    Args:
        user_id: Student ID
        session_id: Current session ID

    Returns:
        Dict or None: Lesson plan JSON
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, plan_json FROM lesson_plans
        WHERE user_id=? AND session_id=?
        ORDER BY id DESC LIMIT 1
    """, (user_id, session_id))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None
    payload = json.loads(row[1])
    payload["lesson_plan_id"] = int(row[0])
    return payload


def get_lesson_plan_cards(user_id: str, lesson_plan_id: int) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id FROM lesson_plans
        WHERE id=? AND user_id=?
        LIMIT 1
        """,
        (lesson_plan_id, user_id),
    )
    if not cursor.fetchone():
        conn.close()
        return []

    cursor.execute(
        """
        SELECT lc.id, lc.card_order, lc.title, lc.card_type, lc.content_json,
               lcp.status, lcp.completed_at
        FROM lesson_cards lc
        LEFT JOIN lesson_card_progress lcp
            ON lcp.card_id = lc.id AND lcp.lesson_plan_id = lc.lesson_plan_id AND lcp.user_id = ?
        WHERE lc.lesson_plan_id=?
        ORDER BY lc.card_order ASC
        """,
        (user_id, lesson_plan_id),
    )
    rows = cursor.fetchall()
    conn.close()

    cards = []
    for row in rows:
        meta = {}
        try:
            meta = json.loads(row[4] or "{}")
        except Exception:
            meta = {}
        cards.append(
            {
                "card_id": int(row[0]),
                "order": int(row[1]),
                "title": row[2],
                "card_type": row[3],
                "content": meta.get("content", ""),
                "status": row[5] or "pending",
                "completed_at": row[6],
            }
        )
    return cards


def complete_lesson_card(user_id: str, lesson_plan_id: int, card_id: int, status: str = "completed") -> Dict:
    now_iso = datetime.now(UTC).isoformat() if status == "completed" else None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id FROM lesson_plans
        WHERE id=? AND user_id=?
        LIMIT 1
        """,
        (lesson_plan_id, user_id),
    )
    if not cursor.fetchone():
        conn.close()
        return {"status": "not_found"}

    cursor.execute(
        """
        INSERT OR REPLACE INTO lesson_card_progress
        (id, user_id, lesson_plan_id, card_id, status, completed_at, created_at)
        VALUES (
            (SELECT id FROM lesson_card_progress WHERE user_id=? AND lesson_plan_id=? AND card_id=?),
            ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
        )
        """,
        (user_id, lesson_plan_id, card_id, user_id, lesson_plan_id, card_id, status, now_iso),
    )
    conn.commit()
    conn.close()
    return {"status": "updated", "card_id": card_id, "lesson_plan_id": lesson_plan_id}


def get_card_for_user(user_id: str, card_id: int) -> Optional[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT lp.id, lp.session_id, lc.id, lc.title, lc.card_type, lc.content_json
        FROM lesson_cards lc
        JOIN lesson_plans lp ON lp.id = lc.lesson_plan_id
        WHERE lc.id=? AND lp.user_id=?
        LIMIT 1
        """,
        (card_id, user_id),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    content_meta = {}
    try:
        content_meta = json.loads(row[5] or "{}")
    except Exception:
        content_meta = {}
    return {
        "lesson_plan_id": int(row[0]),
        "session_id": row[1],
        "card_id": int(row[2]),
        "title": row[3],
        "card_type": row[4],
        "content": content_meta.get("content", ""),
    }


# -------------------------
# Update Step Progress
# -------------------------
def update_step_progress(user_id: str, session_id: str, step_id: int, status: str) -> Dict:
    """
    Mark a lesson step as pending/completed/review.

    Args:
        user_id: Student ID
        session_id: Current session ID
        step_id: Step index in lesson plan
        status: New status ('pending', 'completed', 'review')

    Returns:
        Dict: Status confirmation
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO lesson_progress (user_id, session_id, step_id, status)
        VALUES (?, ?, ?, ?)
    """, (user_id, session_id, step_id, status))
    conn.commit()
    conn.close()
    return {"status": "updated"}


# -------------------------
# Get Next Step
# -------------------------
def get_next_step(user_id: str, session_id: str) -> Optional[Dict]:
    """
    Determine the next pending step for the user in the lesson plan.

    Args:
        user_id: Student ID
        session_id: Current session ID

    Returns:
        Dict: Next step or completion message
    """
    plan = get_lesson_plan(user_id, session_id)
    if not plan:
        return None

    conn = get_connection()
    cursor = conn.cursor()
    for step in plan["steps"]:
        cursor.execute("""
            SELECT status FROM lesson_progress
            WHERE user_id=? AND session_id=? AND step_id=?
            ORDER BY id DESC LIMIT 1
        """, (user_id, session_id, step["id"]))
        row = cursor.fetchone()
        if not row or row[0] != "completed":
            return step

    return {"message": "Lesson completed"}


# -------------------------
# Additional Utilities
# -------------------------
def reset_lesson_progress(user_id: str, session_id: str) -> Dict:
    """
    Reset all steps in a lesson plan to 'pending'.
    Useful for re-studying or revision.

    Args:
        user_id: Student ID
        session_id: Current session ID

    Returns:
        Dict: Status
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM lesson_progress
        WHERE user_id=? AND session_id=?
    """, (user_id, session_id))
    conn.commit()
    conn.close()
    return {"status": "progress reset"}


