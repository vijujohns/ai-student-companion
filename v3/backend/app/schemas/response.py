"""
Response models for standardized output
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any, List, Dict


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error message")

    model_config = ConfigDict(json_schema_extra={"example": {"error": "Invalid credentials"}})


class SuccessResponse(BaseModel):
    """Standard success response"""
    status: str = Field(..., description="Status message")
    data: Optional[Any] = Field(None, description="Optional response data")

    model_config = ConfigDict(json_schema_extra={"example": {"status": "success", "data": None}})


class LoginResponse(BaseModel):
    """Login response"""
    access_token: str = Field(...)
    token_type: str = Field(...)
    role: str = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIs...",
                "token_type": "bearer",
                "role": "student"
            }
        }
    )


class AskResponse(BaseModel):
    """Ask endpoint response"""
    answer: str = Field(...)
    session_id: str = Field(...)
    model_used: Optional[str] = Field(None)
    cached: bool = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answer": "Photosynthesis is the process...",
                "session_id": "uuid-here",
                "model_used": "tinyllama",
                "cached": False
            }
        }
    )


class SessionInfo(BaseModel):
    """Session information"""
    id: str = Field(...)
    title: str = Field(...)
    last_updated: Optional[str] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "uuid-here",
                "title": "Biology - Chapter 5",
                "last_updated": "2024-01-15T10:30:00"
            }
        }
    )


class SessionListResponse(BaseModel):
    """Session list response"""
    sessions: List[SessionInfo] = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sessions": [
                    {
                        "id": "uuid-1",
                        "title": "Biology - Chapter 5",
                        "last_updated": "2024-01-15T10:30:00"
                    },
                    {
                        "id": "uuid-2",
                        "title": "Chemistry - Chapter 3",
                        "last_updated": "2024-01-14T15:45:00"
                    }
                ]
            }
        }
    )


class SessionContentResponse(BaseModel):
    """Session content response"""
    session_content: Optional[str] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={"example": {"session_content": "/knowledge_base/Class-10/Biology/Chapter-5/notes.pdf"}}
    )


class QuizQuestion(BaseModel):
    """Quiz question structure"""
    id: str = Field(...)
    question: str = Field(...)
    options: List[str] = Field(...)
    correct_option: Optional[str] = Field(None)  # Only populated in submission responses

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "q1",
                "question": "What is photosynthesis?",
                "options": ["A) Plant growth", "B) Energy conversion", "C) Water absorption", "D) None of the above"],
                "correct_option": None
            }
        }
    )


class QuizResponse(BaseModel):
    """Quiz generation response"""
    quiz_id: Optional[str] = Field(None)
    quiz: List[QuizQuestion] = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "quiz": [
                    {
                        "id": "q1",
                        "question": "What is photosynthesis?",
                        "options": ["A) Plant growth", "B) Energy conversion", "C) Water absorption", "D) None of the above"],
                        "correct_option": None
                    }
                ]
            }
        }
    )


class QuizSubmitResponse(BaseModel):
    """Quiz submission response"""
    score: int = Field(...)
    total: int = Field(...)
    percentage: float = Field(...)
    details: List[Dict[str, Any]] = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "score": 8,
                "total": 10,
                "percentage": 80.0,
                "details": [
                    {
                        "question": "What is photosynthesis?",
                        "user_answer": "B",
                        "correct_answer": "B",
                        "is_correct": True
                    }
                ]
            }
        }
    )


class LessonStep(BaseModel):
    """Lesson plan step"""
    step_id: int = Field(...)
    title: str = Field(...)
    content: str = Field(...)
    status: Optional[str] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "step_id": 1,
                "title": "Introduction to Photosynthesis",
                "content": "Photosynthesis is...",
                "status": "not_started"
            }
        }
    )


class LessonPlanResponse(BaseModel):
    """Lesson plan response"""
    session_id: str = Field(...)
    chapter: str = Field(...)
    steps: List[LessonStep] = Field(...)
    current_step: Optional[int] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "uuid-here",
                "chapter": "Photosynthesis",
                "steps": [
                    {
                        "step_id": 1,
                        "title": "Introduction",
                        "content": "...",
                        "status": "not_started"
                    }
                ],
                "current_step": 0
            }
        }
    )


class ClassResponse(BaseModel):
    """Available classes response"""
    classes: List[str] = Field(...)

    model_config = ConfigDict(
        json_schema_extra={"example": {"classes": ["Class-8", "Class-9", "Class-10", "Class-11"]}}
    )


class SubjectResponse(BaseModel):
    """Available subjects response"""
    subjects: List[str] = Field(...)

    model_config = ConfigDict(
        json_schema_extra={"example": {"subjects": ["Biology", "Chemistry", "Physics", "Mathematics"]}}
    )


class ContentItem(BaseModel):
    """Content item (PDF, etc.)"""
    title: str = Field(...)
    path: str = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Chapter 5 Notes",
                "path": "/knowledge_base/Class-10/Biology/Chapter-5/notes.pdf"
            }
        }
    )


class ContentsResponse(BaseModel):
    """Contents listing response"""
    contents: List[ContentItem] = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contents": [
                    {"title": "Chapter 5 Notes", "path": "/knowledge_base/Class-10/Biology/Chapter-5/notes.pdf"},
                    {"title": "Practice Questions", "path": "/knowledge_base/Class-10/Biology/Chapter-5/practice.pdf"}
                ]
            }
        }
    )
