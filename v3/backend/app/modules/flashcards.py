# flashcards.py
import os
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from ..modules.dependencies import get_current_user
from pydantic import BaseModel, ConfigDict
from .model_manager import generate_response
from .db import get_connection
from .policy import consume_quota, release_usage
from .messages import get_message
from .analytics import log_activity
#from .history import save_flashcards
from .ingestion import extract_text_from_pdf

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


def _consume_quota_or_raise(user_id: str, action: str) -> None:
    allowed, message_id = consume_quota(user_id, action)
    if allowed:
        return

    msg = get_message(message_id)
    raise HTTPException(
        status_code=429,
        detail={
            "message_id": msg["message_id"],
            "level": msg["level"],
            "message": msg["user_text"],
        },
    )

# ---------- Request / Response Schemas ----------
class FlashcardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_name: str                 # e.g., "Class 8"
    subject: str                    # e.g., "English-1"
    content_type: str               # e.g., "Text Books", "Notes", "QuestionPapers"
    chapter: Optional[str] = None   # optional
    num_cards: Optional[int] = 10
    session_id: Optional[str] = None

class FlashcardItem(BaseModel):
    question: str
    answer: str

class FlashcardResponse(BaseModel):
    flashcards: List[FlashcardItem]

# ---------- Helper Functions ----------
def resolve_files(base_path: str, req: FlashcardRequest) -> List[str]:
    """
    Resolve the files based on class, subject, content_type, and optional chapter.
    Validates each component to prevent path traversal attacks.
    """
    for component in (req.class_name, req.subject, req.content_type):
        if not component or ".." in component or any(c in component for c in ("/", "\\")):
            raise HTTPException(status_code=400, detail="Invalid path component")
    path = os.path.abspath(os.path.join(base_path, req.class_name, req.subject, req.content_type))
    if not path.startswith(os.path.abspath(base_path) + os.sep):
        raise HTTPException(status_code=400, detail="Invalid path component")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No content found")

    files = []
    for f in os.listdir(path):
        full_path = os.path.join(path, f)
        if os.path.isfile(full_path) and f.lower().endswith(".pdf"):
            if req.chapter:
                if req.chapter.lower() in f.lower():
                    files.append(full_path)
            else:
                files.append(full_path)
    return files

def extract_text_from_files(file_paths: List[str]) -> str:
    """
    Extract text from multiple PDFs and concatenate.
    """
    all_text = ""
    for file_path in file_paths:
        text = extract_text_from_pdf(file_path)
        all_text += text + "\n\n"
    return all_text

def generate_flashcards_from_text(text: str, num_cards: int) -> List[FlashcardItem]:
    """
    Generate flashcards using the default LLM.
    """
    # Cap context to keep prompt fast on the local model (~600 tokens)
    capped = text[:2400].strip()
    prompt = (
        f"Generate {num_cards} concise question-answer flashcards from the provided context. "
        "Use exactly this format: Q1: ... A1: ... Q2: ... A2: ..."
    )
    response = generate_response(context=capped, query=prompt, task="flashcards")
    
    # Parse the output into flashcards
    flashcards = []
    lines = response.split("\n")
    q, a = None, None
    for line in lines:
        line = line.strip()
        if line.startswith("Q") and ":" in line:
            q = line.split(":", 1)[1].strip()
        elif line.startswith("A") and ":" in line:
            a = line.split(":", 1)[1].strip()
        if q and a:
            flashcards.append(FlashcardItem(question=q, answer=a))
            q, a = None, None
    return flashcards

def _save_flashcards_artifact(user_id: str, session_id: str, title: str, flashcards: List[FlashcardItem], selected_content: Optional[str] = None):
    """Persist flashcards as a durable learning artifact for a given user/session."""
    conn = get_connection()
    cursor = conn.cursor()
    payload = {
        "flashcards": [
            {
                "question": card.question,
                "answer": card.answer,
            }
            for card in flashcards
        ]
    }
    cursor.execute(
        """
        INSERT INTO learning_artifacts
        (user_id, session_id, lesson_plan_id, card_id, artifact_type, title, payload_json, selected_content, created_at, updated_at)
        VALUES (?, ?, NULL, NULL, 'FLASHCARD', ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (user_id, session_id, title, json.dumps(payload), selected_content),
    )
    conn.commit()
    conn.close()


# ---------- API Endpoint ----------
@router.post("/", response_model=FlashcardResponse)
async def generate_flashcards(req: FlashcardRequest, user=Depends(get_current_user)):
    """Generate flashcards — requires authentication."""
    BASE_KB = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../knowledge_base"))
    files = resolve_files(BASE_KB, req)
    if not files:
        raise HTTPException(status_code=404, detail="No matching files found for flashcard generation.")

    _consume_quota_or_raise(user["username"], "flashcard")
    try:
        text = extract_text_from_files(files)
        flashcards = generate_flashcards_from_text(text, req.num_cards or 10)

        if req.session_id:
            title = f"Flashcards - {req.chapter}" if req.chapter else f"Flashcards - {req.subject}"
            selected_content = f"{req.class_name}/{req.subject}/{req.content_type}/{req.chapter}" if req.chapter else f"{req.class_name}/{req.subject}/{req.content_type}"
            _save_flashcards_artifact(user["username"], req.session_id, title, flashcards, selected_content)

        try:
            log_activity(
                user["username"],
                "flashcard",
                req.subject or "",
                req.chapter or req.subject or "",
                120,
            )
        except Exception:
            pass
    except Exception:
        release_usage(user["username"], "flashcard")
        raise

    return FlashcardResponse(flashcards=flashcards)
