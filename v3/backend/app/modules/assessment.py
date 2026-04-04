"""
Assessment module: subject-level quizzes and structured question papers.

Extends quiz.py to support:
- Multi-chapter subject quizzes with difficulty levels and per-question explanations
- Structured question papers with configurable sections (MCQ / short / long)
- Practice mode (answer revealed per question) vs exam mode (submit all at end)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from .db import get_connection
from .rag import retrieve_chunks
from .model_manager import generate_response
import json
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DIFFICULTY_LEVELS = ("easy", "medium", "hard", "mixed")
MODES = ("practice", "exam")

DEFAULT_PAPER_SECTIONS = [
    {"name": "Section A", "description": "Multiple Choice Questions", "marks_per_q": 1, "count": 10},
    {"name": "Section B", "description": "Short Answer Questions",    "marks_per_q": 3, "count": 5},
    {"name": "Section C", "description": "Long Answer Questions",     "marks_per_q": 5, "count": 4},
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_json(text: str, fallback: Any = None) -> Any:
    """Parse JSON from LLM output, handling markdown fences and stray text."""
    try:
        return json.loads(text)
    except Exception:
        pass
    # Strip markdown code fences if present
    stripped = text.strip()
    for fence in ("```json", "```"):
        if stripped.startswith(fence):
            stripped = stripped[len(fence):]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    try:
        return json.loads(stripped.strip())
    except Exception:
        return fallback


def _normalize_mcq(item: Dict, idx: int, difficulty: str = "mixed") -> Dict:
    """Normalise a single MCQ dict from LLM output into a stable shape."""
    options = item.get("options", [])
    if not isinstance(options, list) or len(options) < 2:
        options = ["Option A", "Option B", "Option C", "Option D"]
    explanation = str(item.get("explanation") or item.get("hint") or "").strip()
    return {
        "id": f"q{idx}",
        "question": str(item.get("question", f"Question {idx}")),
        "options": options[:4],
        "correct_option": str(item.get("answer") or item.get("correct_option") or options[0]),
        "explanation": explanation,
        "difficulty": str(item.get("difficulty") or difficulty),
        "chapter": str(item.get("chapter") or ""),
        "marks": int(item.get("marks") or 1),
    }


def _build_fallback_mcqs(count: int, subject: str, difficulty: str) -> List[Dict]:
    return [
        {
            "id": f"q{i}",
            "question": f"Sample question {i} on {subject}",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_option": "Option A",
            "explanation": "",
            "difficulty": difficulty if difficulty != "mixed" else ("easy" if i % 3 == 0 else "medium"),
            "chapter": "",
            "marks": 1,
        }
        for i in range(1, count + 1)
    ]


def _retrieve_subject_context(subject: str, class_name: str) -> str:
    """Retrieve RAG chunks for a broad subject query."""
    query = f"{subject} {class_name}" if class_name else subject
    chunks = retrieve_chunks(query)
    return " ".join((chunks or [])[:5])


def _summarize_attempts(attempts: Any, fallback: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build stable attempt-summary metadata for history cards and review screens."""
    normalized: List[Dict[str, Any]] = []
    for item in attempts or []:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "score_pct": max(0, min(100, int(item.get("score_pct") or 0))),
                "recorded_at": str(item.get("recorded_at") or "").strip(),
            }
        )

    if normalized:
        recent = list(reversed(normalized[-3:]))
        return {
            "attempt_count": len(normalized),
            "best_score_pct": max(item["score_pct"] for item in normalized),
            "last_score_pct": normalized[-1]["score_pct"],
            "last_attempted_at": normalized[-1]["recorded_at"] or None,
            "recent_scores": [item["score_pct"] for item in recent],
        }

    fallback = fallback or {}
    if not isinstance(fallback, dict) or int(fallback.get("attempt_count") or 0) <= 0:
        return {}

    recent_scores = [
        max(0, min(100, int(score or 0)))
        for score in (fallback.get("recent_scores") or [])[:3]
    ]
    return {
        "attempt_count": int(fallback.get("attempt_count") or 0),
        "best_score_pct": max(0, min(100, int(fallback.get("best_score_pct") or 0))),
        "last_score_pct": max(0, min(100, int(fallback.get("last_score_pct") or 0))),
        "last_attempted_at": fallback.get("last_attempted_at") or None,
        "recent_scores": recent_scores,
    }


# ---------------------------------------------------------------------------
# Subject-level quiz
# ---------------------------------------------------------------------------

def generate_subject_quiz(
    user_id: str,
    session_id: Optional[str],
    subject: str,
    class_name: Optional[str] = None,
    num_questions: int = 10,
    difficulty: str = "mixed",
    mode: str = "practice",
    model_name: Optional[str] = None,
) -> Dict:
    """
    Generate a cross-chapter subject-level quiz.

    Returns a dict with:
        paper_id, paper_type, subject, class_name, mode, difficulty, questions[]
    Each question has: id, question, options, correct_option, explanation, difficulty, chapter, marks.
    """
    num_questions = max(1, min(num_questions, 30))
    difficulty = difficulty if difficulty in DIFFICULTY_LEVELS else "mixed"
    mode = mode if mode in MODES else "practice"

    context = _retrieve_subject_context(subject, class_name or "")
    difficulty_hint = (
        f"Include a mix of easy, medium, and hard questions."
        if difficulty == "mixed"
        else f"All questions should be {difficulty} difficulty."
    )
    prompt = (
        f"Generate {num_questions} multiple-choice quiz questions for the subject '{subject}'"
        + (f" (class/grade: {class_name})" if class_name else "")
        + f".\n{difficulty_hint}\n"
        f"For each question include: question, options (4 choices), answer (exact text of correct option),"
        f" explanation (1-2 sentences), difficulty (easy/medium/hard), chapter (topic area).\n"
        f"Context: {context[:800]}\n"
        f'Return ONLY valid JSON: {{"questions":[{{"question":"...","options":["..."],"answer":"...","explanation":"...","difficulty":"...","chapter":"..."}}]}}'
    )

    raw = ""
    try:
        raw = generate_response(context=context, query=prompt, model_name=model_name, task="quiz")
        parsed = _safe_json(raw, {})
        items = parsed.get("questions") or []
    except Exception as exc:
        logger.warning("LLM subject quiz failed: %s", exc)
        items = []

    questions = [_normalize_mcq(item, idx, difficulty) for idx, item in enumerate(items[:num_questions], 1)]
    while len(questions) < num_questions:
        questions.extend(_build_fallback_mcqs(num_questions - len(questions), subject, difficulty))
    questions = questions[:num_questions]

    paper = {
        "paper_type": "SUBJECT_QUIZ",
        "subject": subject,
        "class_name": class_name or "",
        "mode": mode,
        "difficulty": difficulty,
        "questions": questions,
    }

    paper_id = _persist_paper(user_id, session_id, "SUBJECT_QUIZ", subject, class_name, difficulty, mode, paper)
    return {"paper_id": paper_id, **paper}


# ---------------------------------------------------------------------------
# Question paper
# ---------------------------------------------------------------------------

def generate_question_paper(
    user_id: str,
    session_id: Optional[str],
    subject: str,
    class_name: Optional[str] = None,
    total_marks: int = 40,
    difficulty: str = "mixed",
    sections_config: Optional[List[Dict]] = None,
    model_name: Optional[str] = None,
) -> Dict:
    """
    Generate a structured question paper with multiple sections and marks.

    Sections default to:
        Section A — 10 × 1-mark MCQs  (10 marks)
        Section B —  5 × 3-mark short answers (15 marks)
        Section C —  3 × 5-mark long answers  (15 marks)

    Returns a dict with paper_id, sections[], total_marks, subject, class_name, difficulty.
    Each section has questions[] where MCQ questions have options/answer and
    short/long questions have answer_key.
    """
    sections_config = sections_config or DEFAULT_PAPER_SECTIONS
    # Clamp total_marks to a reasonable range
    total_marks = max(10, min(total_marks, 200))
    difficulty = difficulty if difficulty in DIFFICULTY_LEVELS else "mixed"

    context = _retrieve_subject_context(subject, class_name or "")

    sections = []
    computed_total = 0

    for sec in sections_config:
        sec_name = sec.get("name", "Section")
        sec_desc = sec.get("description", "")
        mpq = int(sec.get("marks_per_q", 1))
        count = int(sec.get("count", 5))
        is_mcq = mpq == 1

        if is_mcq:
            q_type_hint = "multiple-choice (provide options list and the correct answer verbatim)"
            answer_note = '"options":["..."],"answer":"exact correct option text"'
        elif mpq <= 3:
            q_type_hint = "short-answer (2-4 sentences expected)"
            answer_note = '"answer_key":"model answer in 2-4 sentences"'
        else:
            q_type_hint = "long-answer (paragraph expected)"
            answer_note = '"answer_key":"detailed model answer"'

        prompt = (
            f"Generate {count} {q_type_hint} questions for {sec_name} of a {subject} exam"
            + (f" (class {class_name})" if class_name else "")
            + f". Each question is worth {mpq} mark(s). Difficulty: {difficulty}.\n"
            f"Context: {context[:600]}\n"
            f'Return ONLY JSON: {{"questions":[{{"question":"...",{answer_note},"difficulty":"..."}}]}}'
        )

        raw = ""
        try:
            raw = generate_response(context=context, query=prompt, model_name=model_name, task="quiz")
            parsed = _safe_json(raw, {})
            raw_qs = parsed.get("questions") or []
        except Exception as exc:
            logger.warning("LLM question paper section '%s' failed: %s", sec_name, exc)
            raw_qs = []

        built = []
        for i, item in enumerate(raw_qs[:count], 1):
            q: Dict[str, Any] = {
                "id": f"{sec_name.replace(' ', '')}{i}",
                "question": str(item.get("question", f"{sec_name} Question {i}")),
                "marks": mpq,
                "difficulty": str(item.get("difficulty") or difficulty or "medium"),
            }
            if is_mcq:
                opts = item.get("options", [])
                opts = opts if isinstance(opts, list) and len(opts) >= 2 else ["Option A", "Option B", "Option C", "Option D"]
                q["options"] = opts[:4]
                q["answer"] = str(item.get("answer") or opts[0])
            else:
                q["answer_key"] = str(item.get("answer_key") or item.get("answer") or "")
            built.append(q)

        # Fallback questions if LLM returned fewer than expected
        while len(built) < count:
            fb_idx = len(built) + 1
            fb_q: Dict[str, Any] = {
                "id": f"{sec_name.replace(' ', '')}{fb_idx}",
                "question": f"{sec_name} practice question {fb_idx} on {subject}",
                "marks": mpq,
                "difficulty": "medium",
            }
            if is_mcq:
                fb_q["options"] = ["Option A", "Option B", "Option C", "Option D"]
                fb_q["answer"] = "Option A"
            else:
                fb_q["answer_key"] = ""
            built.append(fb_q)

        section_marks = mpq * count
        computed_total += section_marks
        sections.append({
            "name": sec_name,
            "description": sec_desc,
            "marks_per_q": mpq,
            "section_total": section_marks,
            "questions": built,
        })

    paper = {
        "paper_type": "QUESTION_PAPER",
        "subject": subject,
        "class_name": class_name or "",
        "difficulty": difficulty,
        "total_marks": computed_total,
        "sections": sections,
    }

    paper_id = _persist_paper(user_id, session_id, "QUESTION_PAPER", subject, class_name, difficulty, "exam", paper)
    return {"paper_id": paper_id, **paper}


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _persist_paper(
    user_id: str,
    session_id: Optional[str],
    paper_type: str,
    subject: str,
    class_name: Optional[str],
    difficulty: str,
    mode: str,
    paper: Dict,
) -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO assessment_papers
                (user_id, session_id, paper_type, subject, class_name, difficulty, mode, paper_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                session_id or "",
                paper_type,
                subject or "",
                class_name or "",
                difficulty,
                mode,
                json.dumps(paper),
            ),
        )
        paper_id = cursor.lastrowid
        conn.commit()
        return paper_id
    finally:
        conn.close()


def record_assessment_attempt(
    user_id: str,
    paper_id: int,
    correct_count: int,
    total_questions: int,
    score_pct: int,
) -> Optional[Dict[str, Any]]:
    """Persist a completed assessment attempt and return updated summary stats."""
    total_questions = max(1, int(total_questions or 1))
    correct_count = max(0, min(int(correct_count or 0), total_questions))
    score_pct = max(0, min(100, int(round(float(score_pct or 0)))))

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT subject, paper_json FROM assessment_papers WHERE id=? AND user_id=? LIMIT 1",
            (paper_id, user_id),
        )
        row = cursor.fetchone()
        if not row:
            return None

        payload = _safe_json(row[1], {}) if isinstance(row[1], str) else {}
        attempts = payload.get("attempts") or []
        if not isinstance(attempts, list):
            attempts = []

        attempt = {
            "correct_count": correct_count,
            "total_questions": total_questions,
            "score_pct": score_pct,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        attempts.append(attempt)

        attempt_summary = _summarize_attempts(attempts)

        payload["attempts"] = attempts
        payload["attempt_summary"] = attempt_summary

        cursor.execute(
            "UPDATE assessment_papers SET paper_json=? WHERE id=? AND user_id=?",
            (json.dumps(payload), paper_id, user_id),
        )
        conn.commit()

        return {
            "paper_id": paper_id,
            "subject": row[0] or "",
            **attempt_summary,
        }
    finally:
        conn.close()


def get_assessment_paper(user_id: str, paper_id: int) -> Optional[Dict]:
    """Retrieve a single assessment paper by ID for the given user."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, paper_type, subject, class_name, difficulty, mode, paper_json, created_at "
            "FROM assessment_papers WHERE id=? AND user_id=? LIMIT 1",
            (paper_id, user_id),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        return None

    data = _safe_json(row[6], {}) if isinstance(row[6], str) else {}
    attempt_summary = _summarize_attempts(data.get("attempts"), data.get("attempt_summary"))
    if attempt_summary:
        data["attempt_summary"] = attempt_summary

    return {
        "paper_id": row[0],
        "paper_type": row[1],
        "subject": row[2],
        "class_name": row[3],
        "difficulty": row[4],
        "mode": row[5],
        "created_at": row[7],
        **data,
    }


def list_assessment_papers(user_id: str, paper_type: Optional[str] = None) -> List[Dict]:
    """List assessment papers for a user, newest first, with summary fields for history cards."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if paper_type:
            cursor.execute(
                "SELECT id, paper_type, subject, class_name, difficulty, mode, created_at, paper_json "
                "FROM assessment_papers WHERE user_id=? AND paper_type=? ORDER BY id DESC",
                (user_id, paper_type),
            )
        else:
            cursor.execute(
                "SELECT id, paper_type, subject, class_name, difficulty, mode, created_at, paper_json "
                "FROM assessment_papers WHERE user_id=? ORDER BY id DESC",
                (user_id,),
            )
        rows = cursor.fetchall()
    finally:
        conn.close()

    summaries: List[Dict[str, Any]] = []
    for row in rows:
        payload = _safe_json(row[7], {}) if isinstance(row[7], str) else {}
        summary = {
            "paper_id": row[0],
            "paper_type": row[1],
            "subject": row[2],
            "class_name": row[3],
            "difficulty": row[4],
            "mode": row[5],
            "created_at": row[6],
        }

        if row[1] == "SUBJECT_QUIZ":
            summary["question_count"] = len(payload.get("questions") or [])
        elif row[1] == "QUESTION_PAPER":
            sections = payload.get("sections") or []
            summary["section_count"] = len(sections)
            summary["total_marks"] = int(
                payload.get("total_marks")
                or sum(int(section.get("section_total") or 0) for section in sections)
                or 0
            )

        attempt_summary = _summarize_attempts(payload.get("attempts"), payload.get("attempt_summary"))
        if attempt_summary:
            summary["attempt_count"] = int(attempt_summary.get("attempt_count") or 0)
            summary["best_score_pct"] = int(attempt_summary.get("best_score_pct") or 0)
            summary["last_score_pct"] = int(attempt_summary.get("last_score_pct") or 0)
            summary["last_attempted_at"] = attempt_summary.get("last_attempted_at")
            summary["recent_scores"] = attempt_summary.get("recent_scores") or []

        summaries.append(summary)

    return summaries
