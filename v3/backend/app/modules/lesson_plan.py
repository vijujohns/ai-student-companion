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
from .file_management import resolve_content_reference
from .rag import retrieve_chunks
from .model_manager import generate_response
from .quiz import generate_quiz, get_quiz, submit_quiz_answer


_SUMMARY_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "has",
    "have", "in", "into", "is", "it", "its", "of", "on", "or", "that", "the", "their",
    "this", "to", "was", "were", "which", "with", "your",
}

_GENERATED_EXAMPLE_NOTE = "Note: This example is added for better understanding and is not from your material."
_EXAMPLE_MARKERS = ("for example", "for instance", "example", "such as")
_TITLE_BREAK_WORDS = {
    "is", "are", "was", "were", "means", "mean", "happens", "happen", "occurs", "occur",
    "when", "why", "how", "can", "helps", "help", "using", "use", "shows", "show", "explains",
    "explain", "allows", "allow", "because",
}


def _contains_example_marker(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in _EXAMPLE_MARKERS)


def _derive_topic_title(group: List[str], chapter: str, idx: int) -> str:
    combined = " ".join(group or [])
    colon_match = re.search(r"\b([A-Za-z][A-Za-z0-9/&\-\s]{2,60}?):", combined)
    if colon_match:
        candidate = re.sub(r"\s+", " ", colon_match.group(1)).strip(" ,.-")
        if candidate and len(candidate.split()) <= 8:
            return candidate[:80]

    first_sentence = group[0] if group else ""
    tokens = re.findall(r"[A-Za-z0-9/&'\-]+", first_sentence)
    collected: List[str] = []
    for token in tokens:
        lowered = token.lower()
        if collected and lowered in _TITLE_BREAK_WORDS:
            break
        if len(token) < 2:
            continue
        collected.append(token)
        if len(collected) >= 5:
            break

    if collected:
        candidate = " ".join(collected).strip(" ,.-")
        if candidate:
            return candidate[0].upper() + candidate[1:]

    return f"{chapter} Topic {idx}"


# -------------------------
# Helper: Default Step Template
# -------------------------
def default_steps() -> List[Dict]:
    """Return generic lesson steps with no content (used only as last resort)."""
    return [
        {"id": 1, "title": "Introduction", "type": "concept", "status": "pending", "content": "", "bullets": [], "numbered": []},
        {"id": 2, "title": "Key Concepts", "type": "concept", "status": "pending", "content": "", "bullets": [], "numbered": []},
        {"id": 3, "title": "Examples / Case Study", "type": "example", "status": "pending", "content": "", "bullets": [], "numbered": []},
        {"id": 4, "title": "Quiz", "type": "quiz", "status": "pending", "content": "", "bullets": [], "numbered": []},
        {"id": 5, "title": "Revision", "type": "revision", "status": "pending", "content": "", "bullets": [], "numbered": []},
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
            "bullets": [],
            "numbered": [],
        })
    return steps


def _normalize_list_items(items) -> List[str]:
    if not isinstance(items, list):
        return []

    normalized = []
    seen = set()
    for item in items:
        text = re.sub(r"\s+", " ", str(item or "")).strip(" -\t\r\n")
        if not text:
            continue
        if not text.endswith((".", "?", "!")):
            text = f"{text}."
        if text.lower() in seen:
            continue
        seen.add(text.lower())
        normalized.append(text[:220])
    return normalized[:6]


def _clean_sentence(sentence: str) -> str:
    text = re.sub(r"\s+", " ", str(sentence or "")).strip()
    text = re.sub(r"^[^A-Za-z0-9]+", "", text)
    text = re.sub(r"\s*([,;:.!?])", r"\1", text)
    return text.strip()


def _top_keywords(sentences: List[str], limit: int = 4) -> List[str]:
    counts: Dict[str, int] = {}
    for sentence in sentences:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9'-]+", sentence.lower()):
            if token in _SUMMARY_STOPWORDS or len(token) < 4:
                continue
            counts[token] = counts.get(token, 0) + 1

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _ in ranked[:limit]]


def _sentence_to_point(sentence: str) -> str:
    cleaned = _clean_sentence(sentence).rstrip(".")
    if not cleaned:
        return ""

    words = cleaned.split()
    snippet = " ".join(words[:18]).rstrip(" ,;:-")
    if len(words) > 18:
        snippet += "..."
    return snippet[:180]


def _build_ordered_items(step_type: str, title: str, bullet_points: List[str]) -> List[str]:
    if step_type != "quiz":
        return []

    ordered = []
    for point in bullet_points[:3]:
        stem = point.rstrip(".")
        if not stem:
            continue
        ordered.append(f"Explain or answer based on this idea: {stem}.")

    if not ordered and title:
        ordered.append(f"Write a short answer about {title.lower()}.")
    return ordered[:3]


def _build_rewritten_content(group: List[str], title: str, step_type: str) -> Dict[str, object]:
    cleaned_sentences = []
    seen = set()
    for sentence in group:
        cleaned = _clean_sentence(sentence)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned_sentences.append(cleaned)

    keywords = _top_keywords(cleaned_sentences)
    bullet_points = _normalize_list_items([_sentence_to_point(sentence) for sentence in cleaned_sentences[:4]])
    ordered = _normalize_list_items(_build_ordered_items(step_type, title, bullet_points))

    summary_parts = []
    if title:
        summary_parts.append(f"In this card, you learn about {title.lower()} in a teacher-style way.")

    if cleaned_sentences:
        summary_parts.append(f"What it means: {cleaned_sentences[0][:180]}")

    if len(cleaned_sentences) > 1:
        follow_up_label = "Why it matters" if step_type != "quiz" else "How to answer it"
        summary_parts.append(f"{follow_up_label}: {cleaned_sentences[1][:180]}")
    elif keywords:
        summary_parts.append(f"It connects to {', '.join(keywords[:3])} in the lesson.")

    example_present = _contains_example_marker(" ".join(cleaned_sentences + bullet_points))
    if step_type in {"concept", "example"} and not example_present:
        bullet_points = _normalize_list_items(
            [
                *bullet_points[:4],
                f"Example: Think of {title.lower()} in a simple everyday situation. {_GENERATED_EXAMPLE_NOTE}",
            ]
        )

    content = " ".join(part.strip() for part in summary_parts if part.strip())[:520]
    return {
        "content": content,
        "bullets": [] if step_type == "quiz" else bullet_points,
        "numbered": ordered,
    }


def _max_ngram_overlap_ratio(source: str, candidate: str, n: int = 7) -> float:
    source_words = re.findall(r"[A-Za-z0-9']+", (source or "").lower())
    cand_words = re.findall(r"[A-Za-z0-9']+", (candidate or "").lower())
    if len(source_words) < n or len(cand_words) < n:
        return 0.0

    source_ngrams = {tuple(source_words[i:i + n]) for i in range(0, len(source_words) - n + 1)}
    cand_ngrams = [tuple(cand_words[i:i + n]) for i in range(0, len(cand_words) - n + 1)]
    if not cand_ngrams:
        return 0.0

    overlap = sum(1 for ng in cand_ngrams if ng in source_ngrams)
    return overlap / max(1, len(cand_ngrams))


def _is_too_extractive(source: str, content: str, bullets: List[str], numbered: List[str]) -> bool:
    merged = " ".join([content or "", " ".join(bullets or []), " ".join(numbered or [])]).strip()
    if not merged or not source:
        return False

    # If most generated n-grams are copied from source, the output is too extractive.
    return _max_ngram_overlap_ratio(source, merged, n=7) >= 0.45


def _rewrite_steps_abstractive(
    chapter: str,
    candidate_steps: List[Dict],
    model_name: Optional[str] = None,
) -> List[Dict]:
    if not candidate_steps:
        return []

    source_blocks = []
    for step in candidate_steps:
        source_blocks.append(
            {
                "id": int(step.get("id", 0) or 0),
                "title": str(step.get("title", "")).strip(),
                "type": str(step.get("type", "concept")).strip() or "concept",
                "source": str(step.get("_source", "")).strip(),
            }
        )

    prompt = f"""
You are an expert teacher writing clean study notes.

Task:
- Rewrite each step below into student-friendly language.
- Keep the same id/title/type for each step.
- Do NOT copy long phrases from source text.

Strict requirements:
- Return valid JSON only.
- Top-level key must be "steps".
- For each step include: id, title, type, content, bullets, numbered.
- content: 2-3 short sentences.
- bullets: 2-4 concise points for concept/example/revision; [] for quiz.
- numbered: [] for concept/example/revision; 2-3 ordered prompts for quiz.
- Avoid repeating source wording. Explain in simpler language.

Chapter: {chapter}

Step Sources:
{json.dumps(source_blocks, ensure_ascii=True)}

Required output format:
{{
  "steps": [
    {{
      "id": 1,
      "title": "...",
      "type": "concept|example|quiz|revision",
      "content": "...",
      "bullets": ["..."],
      "numbered": ["..."]
    }}
  ]
}}
"""

    try:
        if model_name:
            rewritten_text = generate_response(context="", query=prompt, model_name=model_name, task="lesson")
        else:
            rewritten_text = generate_response(context="", query=prompt, task="lesson")
    except Exception:
        return []

    parsed = _extract_json_from_text(rewritten_text or "")
    if not isinstance(parsed, dict) or not isinstance(parsed.get("steps"), list):
        return []

    by_id = {int(s.get("id", 0) or 0): s for s in candidate_steps}
    accepted = []
    for raw in parsed.get("steps", []):
        try:
            sid = int(raw.get("id", 0) or 0)
        except Exception:
            sid = 0
        original = by_id.get(sid)
        if not original:
            continue

        content = str(raw.get("content", "")).strip()
        bullets = _normalize_list_items(raw.get("bullets", []))
        numbered = _normalize_list_items(raw.get("numbered", []))

        if _is_too_extractive(str(original.get("_source", "")), content, bullets, numbered):
            continue

        accepted.append(
            {
                "id": int(original.get("id", sid)),
                "title": str(raw.get("title", original.get("title", f"Step {sid}")))[:120],
                "type": str(raw.get("type", original.get("type", "concept"))),
                "status": str(original.get("status", "pending")),
                "content": content,
                "bullets": bullets,
                "numbered": numbered,
            }
        )

    min_required = 1 if len(candidate_steps) == 1 else max(2, len(candidate_steps) // 2)
    if len(accepted) < min_required:
        return []

    accepted.sort(key=lambda step: step.get("id", 0))
    return accepted


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
        structured = {
            "content": content,
            "bullets": [],
            "numbered": [],
        }
        steps.append({
            "id": idx,
            "title": title,
            "type": stype,
            "status": "pending",
            "content": structured["content"],
            "bullets": structured["bullets"],
            "numbered": structured["numbered"],
        })
    return steps


def _to_sentences(text: str) -> List[str]:
    """Split text into readable sentence-like units."""
    normalized = re.sub(r"\s+", " ", (text or "")).strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[\.!?])\s+", normalized)
    return [p.strip() for p in parts if p.strip()]


def _infer_step_type(title: str, content: str) -> str:
    lowered = f"{title} {content}".lower()
    if any(k in lowered for k in ["question", "quiz", "exercise", "practice", "mcq"]):
        return "quiz"
    if any(k in lowered for k in ["example", "case", "application", "activity"]):
        return "example"
    if any(k in lowered for k in ["summary", "recap", "revision", "review", "conclusion"]):
        return "revision"
    return "concept"


def _build_summary_step(chapter: str, steps: List[Dict]) -> Dict[str, object]:
    topic_titles = [
        str(step.get("title", "")).strip()
        for step in steps
        if str(step.get("type", "concept")) != "revision" and str(step.get("title", "")).strip()
    ]
    preview = ", ".join(topic_titles[:4]) if topic_titles else chapter
    bullets = _normalize_list_items([f"Quick revision: remember the key idea from {title}" for title in topic_titles[:6]])
    return {
        "step_id": len(steps) + 1,
        "title": "Summary & Quick Revision",
        "type": "revision",
        "status": "pending",
        "content": f"This lesson on {chapter} is easier to revise when you review one key idea at a time. Focus on {preview}.",
        "bullets": bullets,
        "numbered": [],
    }


def _ensure_card_requirements(steps: List[Dict], chapter: str) -> List[Dict]:
    prepared = []
    for idx, step in enumerate(steps, start=1):
        current = {
            "step_id": int(step.get("step_id", step.get("id", idx))),
            "title": str(step.get("title", f"Step {idx}")),
            "type": str(step.get("type", "concept")),
            "status": str(step.get("status", "pending")),
            "content": str(step.get("content", "")).strip(),
            "bullets": _normalize_list_items(step.get("bullets", [])),
            "numbered": _normalize_list_items(step.get("numbered", [])),
        }
        if not current["content"]:
            current["content"] = f"In this card, you learn about {current['title'].lower()} in a simple, student-friendly way."
        prepared.append(current)

    if not prepared:
        return default_steps()

    non_revision = [step for step in prepared if step.get("type") != "revision"]
    if non_revision and not any(step.get("type") == "example" for step in non_revision):
        example_step = non_revision[min(len(non_revision) - 1, max(0, len(non_revision) // 2))]
        example_step["type"] = "example"
        merged = " ".join([example_step.get("content", ""), *example_step.get("bullets", [])]).lower()
        if "not from your material" not in merged:
            example_step["bullets"] = _normalize_list_items(
                [
                    *example_step.get("bullets", [])[:4],
                    f"Example: Think of {example_step['title'].lower()} in a simple everyday situation. {_GENERATED_EXAMPLE_NOTE}",
                ]
            )

    summary_candidates = [step for step in prepared if step.get("type") == "revision"]
    main_steps = [step for step in prepared if step.get("type") != "revision"]
    summary_step = summary_candidates[-1] if summary_candidates else _build_summary_step(chapter, main_steps)
    summary_step["title"] = "Summary & Quick Revision"
    if not summary_step.get("content"):
        summary_step["content"] = _build_summary_step(chapter, main_steps)["content"]
    if not summary_step.get("bullets"):
        summary_step["bullets"] = _build_summary_step(chapter, main_steps)["bullets"]

    final_steps = [*main_steps, summary_step]
    for idx, step in enumerate(final_steps, start=1):
        step["step_id"] = idx
    return final_steps


def _build_adaptive_steps_with_content(chunks: List[str], chapter: str) -> List[Dict]:
    """
    Build context-tailored lesson steps from retrieved chunks.
    Unlike the default template, step count and titles adapt to chapter content.
    """
    valid_chunks = [re.sub(r"\s+", " ", (c or "")).strip() for c in chunks if (c or "").strip()]
    if not valid_chunks:
        return default_steps()

    topic_count = max(2, min(6, len(valid_chunks)))

    all_sentences: List[str] = []
    for chunk in valid_chunks:
        all_sentences.extend(_to_sentences(chunk))

    if not all_sentences:
        return _default_steps_with_content(valid_chunks, chapter)

    group_size = max(1, len(all_sentences) // topic_count)
    steps: List[Dict] = []
    cursor = 0

    for idx in range(1, topic_count + 1):
        if idx == topic_count:
            group = all_sentences[cursor:]
        else:
            group = all_sentences[cursor:cursor + group_size]
        cursor += group_size

        if not group:
            break

        title = _derive_topic_title(group, chapter, idx)
        step_type = _infer_step_type(title, " ".join(group))
        structured = _build_rewritten_content(group, title, step_type)
        steps.append(
            {
                "id": idx,
                "title": title,
                "type": step_type,
                "status": "pending",
                "content": structured["content"],
                "bullets": structured["bullets"],
                "numbered": structured["numbered"],
                "_source": " ".join(group).strip()[:1400],
            }
        )

    return _ensure_card_requirements(steps or _default_steps_with_content(valid_chunks, chapter), chapter)


def _normalize_steps(steps: List[Dict]) -> List[Dict]:
    normalized = []
    for idx, step in enumerate(steps, start=1):
        bullets = _normalize_list_items(step.get("bullets", []))
        numbered = _normalize_list_items(step.get("numbered", []))
        normalized.append(
            {
                "step_id": int(step.get("id", idx)),
                "title": str(step.get("title", f"Step {idx}")),
                "type": str(step.get("type", "concept")),
                "status": str(step.get("status", "pending")),
                "content": str(step.get("content", "")),
                "bullets": bullets,
                "numbered": numbered,
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
                "bullets": step.get("bullets", []),
                "numbered": step.get("numbered", []),
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
    selected_content: Optional[str] = None,
    requested_by: Optional[Dict[str, str]] = None,
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

    resolved_selected_content = None
    selected_content_path = None
    if selected_content:
        try:
            resolved_selected_content = resolve_content_reference(requested_by or {"username": user_id}, selected_content)
            selected_content = str(resolved_selected_content.get("content_id") or selected_content)
            selected_content_path = str(resolved_selected_content.get("path") or "").strip() or None
        except Exception:
            selected_content_path = None

    # 🔹 Retrieve chapter content (RAG)
    chunks = retrieve_chunks(chapter, filter_path=selected_content_path)
    context = "\n\n".join(f"- {chunk}" for chunk in chunks[:12])  # keep topic boundaries readable for the model

    context_hint = (lesson_context or "").strip()

    # 🔹 Build prompt for LLM
    prompt = f"""
You are an AI tutor preparing a student-friendly lesson plan from the provided chapter content.

Strict requirements:
- Use only the provided content as the grounding source.
- Identify ALL main topics in the material before writing.
- Create one card per main topic so no major topic is missed.
- Add a final summary card at the end for quick revision.
- Use a teacher-style explanation for every card.
- Each non-summary card should explain what the topic is, why it matters, and how it works where relevant.
- Each non-summary card should include at least one example.
- If an example is not clearly from the material, add this exact note: "{_GENERATED_EXAMPLE_NOTE}"
- Keep the writing simple, clear, and easy for students to follow.
- Use bullets or numbered lists where they help readability.
- Return valid JSON only (no markdown, no commentary).
- JSON must be an object with a top-level key "steps".
- Each step must include: title, type, content, bullets, numbered.
- Allowed step types: concept, example, quiz, revision.
- "content" must be a clean 2-4 sentence rewritten summary.
- "bullets" must be an array of key points when unordered facts matter, otherwise [].
- "numbered" must be an array for ordered instructions, practice items, or sequences when they matter, otherwise [].
- Do not copy long phrases directly from the source.

Preferred Lesson Focus (optional):
{context_hint or "No special focus provided."}

Chapter Content:
{context}

Required Output Format:
{{
    "steps": [
        {{
            "title": "<specific topic title>",
            "type": "concept|example|quiz|revision",
            "content": "<teacher-style explanation>",
            "bullets": ["<key point or example>"],
            "numbered": ["<ordered item if needed>"]
        }}
    ]
}}
"""

    try:
        if model_name:
            plan_text = generate_response(context=context, query=prompt, model_name=model_name, task="lesson")
        else:
            plan_text = generate_response(context=context, query=prompt, task="lesson")
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

    # Last fallback: build adaptive steps from retrieved chapter content.
    if not steps:
        adaptive_steps = _build_adaptive_steps_with_content(chunks, chapter) if chunks else default_steps()
        rewritten_steps = _rewrite_steps_abstractive(chapter, adaptive_steps, model_name=model_name)
        steps = rewritten_steps or adaptive_steps

    steps = _ensure_card_requirements(_normalize_steps(steps), chapter)

    # 🔹 Construct final lesson plan
    plan = {
        "session_id": session_id,
        "chapter": chapter,
        "selected_content": selected_content,
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
    
    # Transform steps to use step_id instead of id for API compatibility
    if "steps" in payload:
        for step in payload["steps"]:
            if "id" in step and "step_id" not in step:
                step["step_id"] = step.pop("id")
    
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
                "bullets": _normalize_list_items(meta.get("bullets", [])),
                "numbered": _normalize_list_items(meta.get("numbered", [])),
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
        "bullets": _normalize_list_items(content_meta.get("bullets", [])),
        "numbered": _normalize_list_items(content_meta.get("numbered", [])),
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
    try:
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
    finally:
        conn.close()


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


