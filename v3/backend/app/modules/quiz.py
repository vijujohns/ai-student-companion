from typing import List, Dict, Optional
from .db import get_connection
from .rag import retrieve_chunks
from .model_manager import generate_response
import json
import re


def _safe_options(raw_options) -> list[str]:
    options = [str(option).strip() for option in (raw_options or []) if str(option).strip()]
    fallback = ["A", "B", "C", "D"]
    while len(options) < 4:
        options.append(fallback[len(options)])
    return options[:4]


def _normalize_answer_label(raw_answer, options: list[str]) -> str:
    answer = str(raw_answer or "A").strip()
    if not answer:
        return "A"
    upper = answer.upper()
    if upper in {"A", "B", "C", "D"}:
        return upper
    for idx, option in enumerate(options[:4]):
        if answer.lower() == str(option).strip().lower():
            return chr(ord("A") + idx)
    return "A"


def _extract_quiz_json(raw_text) -> dict:
    if isinstance(raw_text, dict):
        return raw_text
    if isinstance(raw_text, list):
        return {"questions": raw_text}

    text = str(raw_text or "").strip()
    if not text:
        return {"questions": []}

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"questions": parsed if isinstance(parsed, list) else []}
    except Exception:
        match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
                return parsed if isinstance(parsed, dict) else {"questions": parsed if isinstance(parsed, list) else []}
            except Exception:
                pass
    return {"questions": []}


def _normalize_questions(raw_questions, num_questions: int = 5):
    """Normalize generated questions into a stable structure."""
    questions = []
    for idx, item in enumerate((raw_questions or [])[:num_questions], start=1):
        if not isinstance(item, dict):
            continue

        options = _safe_options(item.get("options", ["A", "B", "C", "D"]))
        correct_label = _normalize_answer_label(
            item.get("correct_answer") or item.get("correct_option") or item.get("answer"),
            options,
        )
        explanation = str(item.get("explanation") or item.get("reason") or "Based on the provided study material.").strip()

        questions.append(
            {
                "id": f"q{idx}",
                "question": str(item.get("question") or f"Question {idx}").strip(),
                "options": options,
                "correct_option": correct_label,
                "correct_answer": correct_label,
                "explanation": explanation,
            }
        )

    # Ensure predictable fallback count
    while len(questions) < num_questions:
        idx = len(questions) + 1
        questions.append(
            {
                "id": f"q{idx}",
                "question": f"Practice question {idx}",
                "options": ["A", "B", "C", "D"],
                "correct_option": "A",
                "correct_answer": "A",
                "explanation": "Based on the available study material.",
            }
        )

    return questions

# -------------------------
# Generate Context-Aware Quiz
# -------------------------
def generate_quiz(
    user_id: str,
    session_id: str,
    chapter: str,
    num_questions: int = 5,
    model_name: Optional[str] = None,
    context_hint: Optional[str] = None,
) -> Dict:
    """
    Generate quiz questions strictly from the chapter context relevant to this step.
    """
    # Retrieve step-related content using RAG (limit chunks to keep prompt small and fast)
    chunks = retrieve_chunks(chapter)
    context = " ".join(chunks[:4])  # 4 chunks keeps prompt under ~600 tokens

    focus = (context_hint or "").strip()
    focus_line = f"Focus on: {focus}" if focus else ""

    prompt = (
        f"Create {num_questions} multiple-choice quiz questions using ONLY the provided context for chapter: {chapter}.\n"
        f"{focus_line}\n"
        "Return ONLY valid JSON in this exact structure:\n"
        '{"questions":[{"question":"...","options":["A","B","C","D"],"correct_answer":"A","explanation":"..."}]}\n'
        "RULES:\n"
        "- Every question must be answerable from the context only.\n"
        "- Always include exactly 4 options.\n"
        "- Always include correct_answer and explanation.\n"
        "- Do not add commentary outside the JSON.\n"
        f"Context:\n{context}\n"
    )

    try:
        quiz_text = generate_response(context=context, query=prompt, model_name=model_name, task="quiz")
        quiz_json = _extract_quiz_json(quiz_text)
    except Exception:
        # Fallback quiz if LLM fails
        quiz_json = {
            "questions": [
                {
                    "question": f"What is the main point of {chapter}?",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "A",
                    "explanation": "Based on the available study material.",
                }
                for _ in range(num_questions)
            ]
        }

    questions = _normalize_questions(quiz_json.get("questions", []), num_questions=num_questions)
    payload = {"questions": questions}

    # Save quiz to DB
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO lesson_quizzes (user_id, session_id, step_id, quiz_json)
        VALUES (?, ?, ?, ?)
    """, (user_id, session_id, 0, json.dumps(payload)))
    quiz_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {"quiz_id": str(quiz_id), "questions": questions}

# -------------------------
# Get Quiz for Step
# -------------------------
def get_quiz(user_id: str, session_id: str, quiz_id: str) -> Optional[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT quiz_json FROM lesson_quizzes
        WHERE id=? AND user_id=? AND session_id=?
        LIMIT 1
    """, (quiz_id, user_id, session_id))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None
    quiz_data = json.loads(row[0])
    return {
        "quiz_id": str(quiz_id),
        "questions": _normalize_questions(quiz_data.get("questions", []), num_questions=len(quiz_data.get("questions", [])) or 5),
    }


def get_latest_quiz_for_session(user_id: str, session_id: str) -> Optional[Dict]:
    """Return the most recently generated quiz for a user session."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, quiz_json
        FROM lesson_quizzes
        WHERE user_id=? AND session_id=?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id, session_id),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    quiz_data = json.loads(row[1])
    questions = quiz_data.get("questions", [])
    return {
        "quiz_id": str(row[0]),
        "questions": _normalize_questions(questions, num_questions=len(questions) or 5),
    }


def list_quiz_sessions(user_id: str) -> List[Dict]:
    """Return saved quiz sessions ordered by most recent quiz."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            q.session_id,
            MAX(q.created_at) AS last_updated,
            MAX(q.id) AS latest_quiz_id,
            (
                SELECT q2.quiz_json
                FROM lesson_quizzes q2
                WHERE q2.user_id=? AND q2.session_id=q.session_id
                ORDER BY q2.id DESC
                LIMIT 1
            ) AS latest_quiz_json,
            (
                SELECT lp.chapter
                FROM lesson_plans lp
                WHERE lp.user_id=? AND lp.session_id=q.session_id
                ORDER BY lp.id DESC
                LIMIT 1
            ) AS chapter,
            (
                SELECT q2.selected_content
                FROM lesson_quizzes q2
                WHERE q2.user_id=? AND q2.session_id=q.session_id
                ORDER BY q2.id DESC
                LIMIT 1
            ) AS selected_content
        FROM lesson_quizzes q
        WHERE q.user_id=?
        GROUP BY q.session_id
        ORDER BY MAX(created_at) DESC
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
                "title": custom_title or (f"Quiz - {chapter}" if chapter else "Quiz Session"),
                "chapter": chapter,
                "last_updated": row[1],
                "latest_quiz_id": str(row[2]) if row[2] is not None else None,
                "selected_content": selected_content,
            }
        )

    return sessions


def rename_quiz_session(user_id: str, session_id: str, title: str) -> Dict:
    """Persist a custom title for all quizzes under a quiz session."""
    cleaned_title = (title or "").strip()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, quiz_json
            FROM lesson_quizzes
            WHERE user_id=? AND session_id=?
            """,
            (user_id, session_id),
        )
        rows = cursor.fetchall()
        if not rows:
            return {"status": "not_found"}

        cursor.execute("BEGIN IMMEDIATE")
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
                UPDATE lesson_quizzes
                SET quiz_json=?
                WHERE id=?
                """,
                (json.dumps(payload), int(row[0])),
            )

        conn.commit()
    finally:
        conn.close()
    return {"status": "updated"}


def delete_quiz_session(user_id: str, session_id: str) -> Dict:
    """Delete quizzes and quiz results for a quiz session."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM lesson_quiz_results
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
    deleted_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return {"status": "deleted", "deleted_quizzes": deleted_rows}

# -------------------------
# Submit Quiz Answer
# -------------------------
def submit_quiz_answer(user_id: str, session_id: str, quiz_id: str, answers: Dict[str, str]) -> Dict:
    """Record user answers for a quiz and return per-question results."""
    quiz = get_quiz(user_id, session_id, quiz_id)
    if not quiz:
        return {}

    results = {}
    conn = get_connection()
    cursor = conn.cursor()

    for q in quiz["questions"]:
        qid = str(q.get("id"))
        if qid not in answers:
            continue

        user_answer = answers[qid]
        correct_answer = q.get("correct_option")
        is_correct = int(str(user_answer).strip() == str(correct_answer).strip())

        cursor.execute(
            """
            INSERT INTO lesson_quiz_results (user_id, session_id, step_id, question, user_answer, correct_answer, is_correct)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, session_id, 0, q.get("question"), user_answer, correct_answer, is_correct),
        )

        results[qid] = {
            "is_correct": bool(is_correct),
            "correct_answer": correct_answer,
            "user_answer": user_answer,
        }

    conn.commit()
    conn.close()

    return results

# -------------------------
# Get Quiz Results
# -------------------------
def get_quiz_results(user_id: str, session_id: str, step_id: int) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT question, user_answer, correct_answer, is_correct
        FROM lesson_quiz_results
        WHERE user_id=? AND session_id=? AND step_id=?
    """, (user_id, session_id, step_id))
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "question": r[0],
            "user_answer": r[1],
            "correct_answer": r[2],
            "is_correct": bool(r[3])
        })
    return results