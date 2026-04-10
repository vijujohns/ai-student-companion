"""
Request models for input validation
"""

import re
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, Dict, Any, List

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE_RE  = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class LoginRequest(BaseModel):
    """Login endpoint validation"""
    email: str = Field(..., max_length=200, description="Email (user ID)")
    password: str = Field(..., max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Email is required.")
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v:
            raise ValueError("Password is required.")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "student@example.com",
                "password": "student123"
            }
        }
    )


class RegisterRequest(BaseModel):
    """User registration validation"""
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: str = Field(..., max_length=200)
    dob: str = Field(..., max_length=20, description="YYYY-MM-DD")
    password: str = Field(..., max_length=128)

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("First name is required.")
        return v.strip()

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Last name is required.")
        return v.strip()

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Email is required.")
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address.")
        return v

    @field_validator("dob")
    @classmethod
    def validate_dob(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Date of birth is required.")
        if not _DATE_RE.match(v):
            raise ValueError("Date of birth must be in YYYY-MM-DD format.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v:
            raise ValueError("Password is required.")
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters.")
        return v
    role: str = Field("student", description="Allowed: student, teacher, parent")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        role = (v or "student").strip().lower()
        if role not in {"student", "teacher", "parent"}:
            raise ValueError("Role must be student, teacher, or parent.")
        return role

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "ada@example.com",
                "dob": "2004-02-14",
                "password": "securePass123",
                "role": "student"
            }
        }
    )


class ResetPasswordRequest(BaseModel):
    """Password reset validation based on email + DOB."""
    email: str = Field(..., max_length=200)
    dob: str = Field(..., max_length=20, description="YYYY-MM-DD")
    new_password: str = Field(..., max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Email is required.")
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address.")
        return v

    @field_validator("dob")
    @classmethod
    def validate_dob(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Date of birth is required.")
        if not _DATE_RE.match(v):
            raise ValueError("Date of birth must be in YYYY-MM-DD format.")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if not v:
            raise ValueError("New password is required.")
        if len(v) < 6:
            raise ValueError("New password must be at least 6 characters.")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "ada@example.com",
                "dob": "2004-02-14",
                "new_password": "newSecurePass123"
            }
        }
    )


class ProfileUpdateRequest(BaseModel):
    """Profile update validation (email is immutable server-side)."""

    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    dob: Optional[str] = Field(None, max_length=20, description="YYYY-MM-DD")
    email: Optional[str] = Field(None, max_length=200)

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("First name cannot be empty.")
        return trimmed

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Last name cannot be empty.")
        return trimmed

    @field_validator("dob")
    @classmethod
    def validate_dob(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        trimmed = v.strip()
        if not _DATE_RE.match(trimmed):
            raise ValueError("Date of birth must be in YYYY-MM-DD format.")
        return trimmed

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        trimmed = v.strip()
        if not _EMAIL_RE.match(trimmed):
            raise ValueError("Enter a valid email address.")
        return trimmed

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "dob": "2004-02-14",
            }
        }
    )


class AskRequest(BaseModel):
    """Ask endpoint validation"""
    query: str = Field(..., min_length=1, max_length=5000, description="The question to ask")
    session_id: Optional[str] = Field(None, max_length=100, description="Session ID (optional)")
    model_name: Optional[str] = Field(None, max_length=50, description="LLM model to use (optional)")
    task: Optional[str] = Field(None, max_length=50, description="Optional task hint such as qa, summary, lesson, or quiz")
    content_id: Optional[str] = Field(None, min_length=1, max_length=1000, description="Selected content reference (optional)")
    bypass_cache: bool = Field(False, description="If true, skip response cache lookup and write for this request")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "Explain photosynthesis",
                "session_id": "uuid-here",
                "model_name": "tinyllama",
                "task": "summary",
                "content_id": "kb:Q2xhc3MtMTAvQmlvbG9neS9DaGFwdGVyLTUvbm90ZXMucGRm",
                "bypass_cache": False
            }
        }
    )


class RenameSessionRequest(BaseModel):
    """Rename session endpoint validation"""
    title: str = Field(..., min_length=1, max_length=200)

    model_config = ConfigDict(
        json_schema_extra={"example": {"title": "Biology - Chapter 5"}}
    )


class SetSessionContentRequest(BaseModel):
    """Update session content endpoint validation"""
    content_id: Optional[str] = Field(None, min_length=1, max_length=1000)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"content_id": "kb:Q2xhc3MtMTAvQmlvbG9neS9DaGFwdGVyLTUvbm90ZXMucGRm"}}
    )


class ContextSelectionRequest(BaseModel):
    """Persist the user's global learning context or Explorer Mode selection."""

    mode: str = Field("contextual", max_length=20)
    class_name: Optional[str] = Field(None, max_length=100)
    subject_name: Optional[str] = Field(None, max_length=100)
    folder_name: Optional[str] = Field(None, max_length=100)
    content_id: Optional[str] = Field(None, min_length=1, max_length=1000)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        normalized = str(v or "contextual").strip().lower()
        if normalized not in {"contextual", "explorer"}:
            raise ValueError("Mode must be contextual or explorer.")
        return normalized

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "mode": "contextual",
                "class_name": "Class 8",
                "subject_name": "Math",
                "folder_name": "Notes",
                "content_id": "upload:12",
            }
        },
    )


class LessonPlanCreateRequest(BaseModel):
    """Create lesson plan endpoint validation"""
    chapter: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = Field(None, max_length=100)
    lesson_context: Optional[str] = Field(None, max_length=1000)
    content_id: Optional[str] = Field(None, min_length=1, max_length=1000)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "chapter": "Photosynthesis",
                "session_id": "uuid-here",
                "lesson_context": "Focus on exam-style questions and simple analogies",
                "content_id": "kb:Q2xhc3MtMTAvQmlvbG9neS9QaG90b3N5bnRoZXNpcy5wZGY"
            }
        }
    )


class LessonProgressRequest(BaseModel):
    """Update lesson progress endpoint validation"""
    session_id: str = Field(..., max_length=100)
    step_id: int = Field(..., ge=0)
    status: str = Field(..., min_length=1, max_length=50)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "uuid-here",
                "step_id": 1,
                "status": "completed"
            }
        }
    )


class QuizGenerateRequest(BaseModel):
    """Generate quiz endpoint validation"""
    session_id: str = Field(..., max_length=100)
    chapter: str = Field(..., min_length=1, max_length=500)
    quiz_context: Optional[str] = Field(None, max_length=1000)
    content_id: Optional[str] = Field(None, min_length=1, max_length=1000)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "uuid-here",
                "chapter": "Photosynthesis",
                "quiz_context": "Focus on tricky exam questions and common mistakes",
                "content_id": "kb:Q2xhc3MtMTAvQmlvbG9neS9QaG90b3N5bnRoZXNpcy5wZGY"
            }
        }
    )


class QuizSubmitRequest(BaseModel):
    """Submit quiz answers endpoint validation"""
    session_id: str = Field(..., max_length=100)
    answers: Dict[str, Any] = Field(..., description="Mapping of question_id to selected_option")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "uuid-here",
                "answers": {
                    "q1": "option_a",
                    "q2": "option_b",
                    "q3": "option_c"
                }
            }
        }
    )


class FlashcardCreateRequest(BaseModel):
    """Create flashcard endpoint validation"""
    chapter: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = Field(None, max_length=100)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "chapter": "Photosynthesis",
                "session_id": "uuid-here"
            }
        }
    )


class ArtifactGenerateRequest(BaseModel):
    """Optional context for card-based quiz or flashcard generation"""
    context: Optional[str] = Field(None, max_length=1000)
    content_id: Optional[str] = Field(None, min_length=1, max_length=1000)


class SubscriptionQuoteRequest(BaseModel):
    """Subscription quote request for one or more classes."""
    class_names: list[str] = Field(..., min_length=1)
    promo_code: Optional[str] = Field(None, max_length=50)
    auto_renew: bool = Field(False)

    @field_validator("class_names")
    @classmethod
    def validate_class_names(cls, values: list[str]) -> list[str]:
        cleaned = [str(value or "").strip() for value in values if str(value or "").strip()]
        if not cleaned:
            raise ValueError("Select at least one class.")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "class_names": ["Class 8", "Class 9"],
                "promo_code": "WELCOME10",
                "auto_renew": True,
            }
        }
    )


class SubscriptionActivateRequest(SubscriptionQuoteRequest):
    """Subscription activation request (post-quote confirmation)."""
    payment_reference: Optional[str] = Field(None, max_length=120)


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------

class SubjectQuizRequest(BaseModel):
    """Generate a subject-level multi-chapter quiz."""
    subject: str = Field(..., min_length=1, max_length=300)
    class_name: Optional[str] = Field(None, max_length=100)
    session_id: Optional[str] = Field(None, max_length=100)
    num_questions: int = Field(10, ge=1, le=30)
    difficulty: str = Field("mixed", max_length=20)
    mode: str = Field("practice", max_length=20)

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        allowed = ("easy", "medium", "hard", "mixed")
        if v not in allowed:
            raise ValueError(f"difficulty must be one of {allowed}")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        allowed = ("practice", "exam")
        if v not in allowed:
            raise ValueError(f"mode must be one of {allowed}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject": "Science",
                "class_name": "Class 10",
                "num_questions": 10,
                "difficulty": "mixed",
                "mode": "practice",
            }
        }
    )


class QuestionPaperRequest(BaseModel):
    """Generate a structured question paper with configurable sections and marks."""
    subject: str = Field(..., min_length=1, max_length=300)
    class_name: Optional[str] = Field(None, max_length=100)
    session_id: Optional[str] = Field(None, max_length=100)
    total_marks: int = Field(40, ge=10, le=200)
    difficulty: str = Field("mixed", max_length=20)
    sections: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Custom sections list; defaults to A/B/C sections if omitted",
    )

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        allowed = ("easy", "medium", "hard", "mixed")
        if v not in allowed:
            raise ValueError(f"difficulty must be one of {allowed}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject": "Mathematics",
                "class_name": "Class 10",
                "total_marks": 40,
                "difficulty": "mixed",
            }
        }
    )


class AssessmentAttemptRequest(BaseModel):
    """Persist the score from a completed assessment attempt."""
    correct_count: int = Field(..., ge=0)
    total_questions: int = Field(..., ge=1)
    score_pct: int = Field(..., ge=0, le=100)

    @model_validator(mode="after")
    def validate_counts(self):
        if self.correct_count > self.total_questions:
            raise ValueError("correct_count cannot exceed total_questions")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "correct_count": 8,
                "total_questions": 10,
                "score_pct": 80,
            }
        }
    )


# ---------------------------------------------------------------------------
# Progress / Analytics
# ---------------------------------------------------------------------------

class LogActivityRequest(BaseModel):
    """Log a study activity with optional duration for progress tracking."""
    activity_type: str = Field(..., max_length=50)
    subject: Optional[str] = Field("", max_length=300)
    chapter: Optional[str] = Field("", max_length=500)
    duration_seconds: int = Field(0, ge=0, le=86400)

    @field_validator("activity_type")
    @classmethod
    def validate_activity_type(cls, v: str) -> str:
        allowed = ("chat", "lesson", "quiz", "flashcard", "assessment", "other")
        if v not in allowed:
            raise ValueError(f"activity_type must be one of {allowed}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "activity_type": "lesson",
                "subject": "Science",
                "chapter": "Photosynthesis",
                "duration_seconds": 300,
            }
        }
    )


class TranslateRequest(BaseModel):
    """Translate arbitrary text to a target language."""
    text: str = Field(..., min_length=1, max_length=8000)
    target_language: str = Field("en", max_length=20)
    source_language: str = Field("auto", max_length=20)

    @field_validator("target_language")
    @classmethod
    def validate_target_language(cls, v: str) -> str:
        from ..modules.translation import SUPPORTED_LANGUAGES
        v = v.strip()
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported target language: '{v}'. Call GET /languages for valid codes.")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "What is photosynthesis?",
                "target_language": "hi",
            }
        }
    )


class ReminderSettingsRequest(BaseModel):
    enabled: bool = True
    frequency: str = Field("daily", max_length=40)
    muted_ids: List[str] = Field(default_factory=list)

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        value = (v or "daily").strip().lower()
        allowed = {"all", "daily", "important-only", "weekly", "off"}
        if value not in allowed:
            raise ValueError(f"Frequency must be one of {sorted(allowed)}.")
        return value

    @field_validator("muted_ids")
    @classmethod
    def validate_muted_ids(cls, v: List[str]) -> List[str]:
        return [item.strip() for item in (v or []) if isinstance(item, str) and item.strip()][:25]


class PreferencesUpdateRequest(BaseModel):
    """Update user preferences."""
    preferred_language: str = Field(..., max_length=20)
    reminder_settings: Optional[ReminderSettingsRequest] = None

    @field_validator("preferred_language")
    @classmethod
    def validate_preferred_language(cls, v: str) -> str:
        from ..modules.translation import SUPPORTED_LANGUAGES
        v = v.strip()
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: '{v}'. Call GET /languages for valid codes.")
        return v


class AdminModelProfileUpdateRequest(BaseModel):
    """Update the globally active model behavior profile."""
    profile_key: str = Field(..., max_length=40)

    @field_validator("profile_key")
    @classmethod
    def validate_profile_key(cls, v: str) -> str:
        from ..modules.model_manager import list_model_profile_keys

        value = (v or "").strip().lower()
        valid = set(list_model_profile_keys())
        if value not in valid:
            raise ValueError(f"Profile key must be one of {sorted(valid)}.")
        return value


class NoteSaveRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    content: str = Field(..., min_length=1, max_length=20000)
    session_id: Optional[str] = Field(None, max_length=100)
    source_query: Optional[str] = Field(None, max_length=1000)
    selected_content: Optional[str] = Field(None, min_length=1, max_length=1000)
    is_pinned: bool = Field(False)

    @field_validator("title")
    @classmethod
    def validate_optional_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = v.strip()
        return value or None

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("Note content is required.")
        return value


class NoteUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = Field(None, min_length=1, max_length=20000)
    source_query: Optional[str] = Field(None, max_length=1000)
    selected_content: Optional[str] = Field(None, min_length=1, max_length=1000)
    is_pinned: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def validate_update_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = v.strip()
        return value or None

    @field_validator("content")
    @classmethod
    def validate_update_content(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = v.strip()
        if not value:
            raise ValueError("Note content cannot be empty.")
        return value

    @model_validator(mode="after")
    def validate_has_update(self):
        if not any(
            getattr(self, field) is not None
            for field in ("title", "content", "source_query", "selected_content", "is_pinned")
        ):
            raise ValueError("Provide at least one field to update.")
        return self


class LinkStudentRequest(BaseModel):
    student_email: str = Field(..., max_length=200)
    relation_label: Optional[str] = Field(None, max_length=80)

    @field_validator("student_email")
    @classmethod
    def validate_student_email(cls, v: str) -> str:
        email = (v or "").strip()
        if not _EMAIL_RE.match(email):
            raise ValueError("Enter a valid student email address.")
        return email

    @field_validator("relation_label")
    @classmethod
    def validate_relation_label(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        label = v.strip()
        return label or None


class CollaborationNoteRequest(BaseModel):
    student_username: str = Field(..., min_length=3, max_length=200)
    note_text: str = Field(..., min_length=1, max_length=2000)
    visibility: str = Field("all", description="all or guardians")

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str) -> str:
        value = (v or "all").strip().lower()
        if value not in {"all", "guardians"}:
            raise ValueError("Visibility must be all or guardians.")
        return value

    model_config = ConfigDict(
        json_schema_extra={"example": {"preferred_language": "hi"}}
    )


class CollaborationNoteUpdateRequest(BaseModel):
    note_text: Optional[str] = Field(None, min_length=1, max_length=2000)
    visibility: Optional[str] = Field(None, description="all or guardians")

    @field_validator("note_text")
    @classmethod
    def validate_note_text(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = v.strip()
        if not value:
            raise ValueError("Note text cannot be empty.")
        return value

    @field_validator("visibility")
    @classmethod
    def validate_optional_visibility(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = v.strip().lower()
        if value not in {"all", "guardians"}:
            raise ValueError("Visibility must be all or guardians.")
        return value

    @model_validator(mode="after")
    def validate_has_update(self):
        if self.note_text is None and self.visibility is None:
            raise ValueError("Provide note_text or visibility to update.")
        return self


class MentorAssignmentRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=120)
    description: str = Field(..., min_length=3, max_length=500)
    action_tab: str = Field("lesson", description="lesson, quiz, assessment, chat, or flashcards")
    cta_label: Optional[str] = Field(None, max_length=80)
    chapter_hint: Optional[str] = Field(None, max_length=120)
    context_hint: Optional[str] = Field(None, max_length=300)
    due_label: Optional[str] = Field(None, max_length=80)

    @field_validator("action_tab")
    @classmethod
    def validate_action_tab(cls, v: str) -> str:
        value = (v or "lesson").strip().lower()
        if value not in {"lesson", "quiz", "assessment", "chat", "flashcards"}:
            raise ValueError("Action tab must be lesson, quiz, assessment, chat, or flashcards.")
        return value


class MentorAssignmentUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=120)
    description: Optional[str] = Field(None, min_length=3, max_length=500)
    action_tab: Optional[str] = Field(None, description="lesson, quiz, assessment, chat, or flashcards")
    cta_label: Optional[str] = Field(None, max_length=80)
    chapter_hint: Optional[str] = Field(None, max_length=120)
    context_hint: Optional[str] = Field(None, max_length=300)
    due_label: Optional[str] = Field(None, max_length=80)
    status: Optional[str] = Field(None, description="assigned, completed, or dismissed")

    @field_validator("action_tab")
    @classmethod
    def validate_optional_action_tab(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = v.strip().lower()
        if value not in {"lesson", "quiz", "assessment", "chat", "flashcards"}:
            raise ValueError("Action tab must be lesson, quiz, assessment, chat, or flashcards.")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = v.strip().lower()
        if value not in {"assigned", "completed", "dismissed"}:
            raise ValueError("Status must be assigned, completed, or dismissed.")
        return value

    @model_validator(mode="after")
    def validate_has_update(self):
        if not any(
            getattr(self, field) is not None
            for field in ("title", "description", "action_tab", "cta_label", "chapter_hint", "context_hint", "due_label", "status")
        ):
            raise ValueError("Provide at least one field to update.")
        return self


class StudyPlanItemUpdateRequest(BaseModel):
    item_type: str = Field("schedule", description="schedule or goal")
    completed: bool = Field(True)

    @field_validator("item_type")
    @classmethod
    def validate_item_type(cls, v: str) -> str:
        value = (v or "schedule").strip().lower()
        if value not in {"schedule", "goal"}:
            raise ValueError("Item type must be schedule or goal.")
        return value
