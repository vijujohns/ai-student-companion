"""
Request models for input validation
"""

import re
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, Dict, Any

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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "ada@example.com",
                "dob": "2004-02-14",
                "password": "securePass123"
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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "Explain photosynthesis",
                "session_id": "uuid-here",
                "model_name": "tinyllama"
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
    path: Optional[str] = Field(None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_content_reference(self):
        if not self.content_id and not self.path:
            raise ValueError("content_id or path is required.")
        return self

    model_config = ConfigDict(
        json_schema_extra={"example": {"content_id": "kb:Q2xhc3MtMTAvQmlvbG9neS9DaGFwdGVyLTUvbm90ZXMucGRm"}}
    )


class LessonPlanCreateRequest(BaseModel):
    """Create lesson plan endpoint validation"""
    chapter: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = Field(None, max_length=100)
    lesson_context: Optional[str] = Field(None, max_length=1000)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "chapter": "Photosynthesis",
                "session_id": "uuid-here",
                "lesson_context": "Focus on exam-style questions and simple analogies"
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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "uuid-here",
                "chapter": "Photosynthesis",
                "quiz_context": "Focus on tricky exam questions and common mistakes"
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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "context": "Keep it concise and focus on likely viva questions"
            }
        }
    )
