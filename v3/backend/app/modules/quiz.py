from typing import List, Dict, Optional
from .db import get_connection
from .file_management import resolve_content_reference
from .rag import retrieve_chunks
from .model_manager import generate_response
from ..core.debug_logger import dwarn
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


def _answer_text_from_label(label: str, options: list[str]) -> str:
    normalized = str(label or "").strip().upper()
    if normalized in {"A", "B", "C", "D"}:
        idx = ord(normalized) - ord("A")
        if 0 <= idx < len(options):
            return str(options[idx]).strip()
    return str(label or "").strip()


def _normalize_submitted_answer(raw_answer, options: list[str]) -> tuple[str, str]:
    answer_text = str(raw_answer or "").strip()
    if not answer_text:
        return "", ""

    label = _normalize_answer_label(answer_text, options)
    normalized_text = _answer_text_from_label(label, options)
    if answer_text.upper() in {"A", "B", "C", "D"}:
        return label, normalized_text

    for option in options[:4]:
        option_text = str(option).strip()
        if answer_text.lower() == option_text.lower():
            return label, option_text

    return label, answer_text


def _trim_text(value: str, limit: int = 96) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip(" ,;:") + "..."


def _extract_plain_text_questions(raw_text: str) -> list[dict]:
    lines = [line.strip() for line in str(raw_text or "").splitlines() if line.strip()]
    if not lines:
        return []

    questions = []
    current: Optional[dict] = None

    for line in lines:
        option_match = re.match(r"^([A-D])[\)\.:-]\s*(.+)$", line, flags=re.IGNORECASE)
        answer_match = re.match(r"^(?:correct\s+answer|answer)\s*[:\-]\s*(.+)$", line, flags=re.IGNORECASE)
        explanation_match = re.match(r"^(?:explanation|reason)\s*[:\-]\s*(.+)$", line, flags=re.IGNORECASE)
        question_match = re.match(r"^(?:\d+[\)\.:-]\s*|q(?:uestion)?\s*\d*[:.-]?\s*)(.+)$", line, flags=re.IGNORECASE)

        if option_match and current is not None:
            current.setdefault("options", []).append(option_match.group(2).strip())
            continue
        if answer_match and current is not None:
            current["correct_answer"] = answer_match.group(1).strip()
            continue
        if explanation_match and current is not None:
            current["explanation"] = explanation_match.group(1).strip()
            continue
        if question_match:
            if current and current.get("question") and current.get("options"):
                questions.append(current)
            current = {"question": question_match.group(1).strip(), "options": []}
            continue
        if current is None and line.endswith("?"):
            current = {"question": line, "options": []}
            continue
        if current is not None and current.get("options") and not current.get("explanation"):
            current["explanation"] = line

    if current and current.get("question") and current.get("options"):
        questions.append(current)

    return questions


def _context_sentence_candidates(context: str) -> list[str]:
    text = re.sub(r"\s+", " ", str(context or "").strip())
    if not text:
        return []

    candidates = []
    seen = set()
    for fragment in re.split(r"(?<=[.!?])\s+", text):
        candidate = re.sub(r"^[\s\-•]+", "", fragment).strip()
        candidate = re.sub(r"\s+", " ", candidate)
        if len(candidate.split()) < 4:
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    return candidates


def _build_grounded_fallback_questions(context: str, chapter: str, count: int, start_index: int = 1) -> list[dict]:
    topic = str(chapter or "this topic").strip() or "this topic"
    facts = _context_sentence_candidates(context)
    if not facts:
        facts = [
            f"The study material discusses {topic}.",
            f"The correct answer must be supported by the lesson on {topic}.",
            "Choose the option that is directly stated in the provided material.",
            "Avoid outside facts that do not appear in the chapter.",
        ]

    stems = [
        f"Which statement is directly supported by the study material about {topic}?",
        f"According to the provided lesson on {topic}, which option is correct?",
        f"Which fact is explicitly mentioned in the chapter about {topic}?",
        f"Based on the study material for {topic}, which statement is accurate?",
    ]

    questions = []
    for offset in range(count):
        idx = start_index + offset
        correct_fact = _trim_text(facts[offset % len(facts)], 88)
        distractors = [_trim_text(item, 88) for item in facts if item != facts[offset % len(facts)]]
        while len(distractors) < 3:
            distractors.append(_trim_text(f"This option adds outside information not stated in the lesson on {topic}.", 88))

        correct_slot = (idx - 1) % 4
        options = distractors[:3]
        options.insert(correct_slot, correct_fact)
        options = options[:4]

        questions.append(
            {
                "id": f"q{idx}",
                "question": stems[(idx - 1) % len(stems)],
                "options": options,
                "correct_option": chr(ord("A") + correct_slot),
                "correct_answer": chr(ord("A") + correct_slot),
                "explanation": correct_fact,
            }
        )

    return questions


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

    plain_text_questions = _extract_plain_text_questions(text)
    if plain_text_questions:
        return {"questions": plain_text_questions}

    return {"questions": []}


def _normalize_questions(raw_questions, num_questions: int = 5, fallback_context: str = "", chapter: str = ""):
    """Normalize generated questions into a stable structure and avoid placeholder-only fallbacks."""
    questions = []
    for item in raw_questions or []:
        if not isinstance(item, dict):
            continue

        question_text = str(item.get("question") or "").strip()
        options = _safe_options(item.get("options", ["A", "B", "C", "D"]))
        explanation = str(item.get("explanation") or item.get("reason") or "Based on the provided study material.").strip()
        if not question_text:
            continue

        generic_shell = options == ["A", "B", "C", "D"]
        generic_explanation = explanation.lower() in {
            "based on the available study material.",
            "based on the provided study material.",
            "a safe fallback response was returned because generation was temporarily unavailable.",
        }
        if question_text.lower().startswith("practice question") or (generic_shell and generic_explanation):
            continue

        idx = len(questions) + 1
        correct_label = _normalize_answer_label(
            item.get("correct_answer") or item.get("correct_option") or item.get("answer"),
            options,
        )

        questions.append(
            {
                "id": f"q{idx}",
                "question": question_text,
                "options": options,
                "correct_option": correct_label,
                "correct_answer": correct_label,
                "explanation": explanation,
            }
        )

        if len(questions) >= num_questions:
            break

    if len(questions) < num_questions:
        missing = num_questions - len(questions)
        dwarn(
            "QUIZ",
            "Quiz generation used grounded fallback questions",
            chapter=chapter or None,
            recovered=len(questions),
            requested=num_questions,
            fallback_count=missing,
            context_chars=len(str(fallback_context or "")),
        )
        questions.extend(
            _build_grounded_fallback_questions(
                fallback_context,
                chapter,
                missing,
                start_index=len(questions) + 1,
            )
        )

    return questions[:num_questions]

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
    selected_content: Optional[str] = None,
    requested_by: Optional[Dict[str, str]] = None,
) -> Dict:
    """
    Generate quiz questions strictly from the chapter context relevant to this step.
    """
    resolved_selected_content = None
    selected_content_path = None
    if selected_content:
        try:
            resolved_selected_content = resolve_content_reference(requested_by or {"username": user_id}, selected_content)
            selected_content = str(resolved_selected_content.get("content_id") or selected_content)
            selected_content_path = str(resolved_selected_content.get("path") or "").strip() or None
        except Exception:
            selected_content_path = None

    # Retrieve step-related content using RAG (limit chunks to keep prompt small and fast)
    chunks = retrieve_chunks(chapter, filter_path=selected_content_path)
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
        if not quiz_json.get("questions"):
            dwarn(
                "QUIZ",
                "Quiz model output was not valid structured content; recovering from context",
                chapter=chapter or None,
                selected_content=selected_content or None,
                response_preview=_trim_text(quiz_text, 160) or None,
            )
    except Exception as exc:
        dwarn(
            "QUIZ",
            "Quiz generation failed; recovering from context",
            chapter=chapter or None,
            selected_content=selected_content or None,
            error=str(exc),
        )
        quiz_json = {"questions": []}

    questions = _normalize_questions(
        quiz_json.get("questions", []),
        num_questions=num_questions,
        fallback_context=context,
        chapter=chapter,
    )
    payload = {"chapter": chapter, "selected_content": selected_content, "questions": questions}

    # Save quiz to DB
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO lesson_quizzes (user_id, session_id, step_id, quiz_json, selected_content)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, session_id, 0, json.dumps(payload), selected_content))
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
        "questions": _normalize_questions(
            quiz_data.get("questions", []),
            num_questions=len(quiz_data.get("questions", [])) or 5,
            chapter=str(quiz_data.get("chapter") or ""),
        ),
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

        options = _safe_options(q.get("options", []))
        user_answer = answers[qid]
        user_label, normalized_user_answer = _normalize_submitted_answer(user_answer, options)

        correct_label = _normalize_answer_label(
            q.get("correct_answer") or q.get("correct_option") or q.get("answer"),
            options,
        )
        correct_answer = _answer_text_from_label(correct_label, options)
        is_correct = int(bool(user_label) and user_label == correct_label)

        cursor.execute(
            """
            INSERT INTO lesson_quiz_results (user_id, session_id, step_id, question, user_answer, correct_answer, is_correct)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, session_id, 0, q.get("question"), normalized_user_answer, correct_answer, is_correct),
        )

        results[qid] = {
            "is_correct": bool(is_correct),
            "correct_answer": correct_answer,
            "correct_option": correct_label,
            "user_answer": normalized_user_answer,
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