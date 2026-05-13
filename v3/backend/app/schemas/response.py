"""
Response models for standardized output
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any, List, Dict


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error message")

    model_config = ConfigDict(json_schema_extra={"example": {"error": "Invalid credentials"}})


class MessageMeta(BaseModel):
    """Standard response envelope metadata"""
    message_id: str = Field(..., description="Message catalog identifier")
    level: str = Field(..., description="Severity level of the message")
    user_text: str = Field(..., description="User-facing message text")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message_id": "MSG-1000",
                "level": "INFO",
                "user_text": "Operation completed successfully."
            }
        }
    )


class PaginationMeta(BaseModel):
    """Offset pagination metadata for mobile-heavy collections."""

    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)
    count: int = Field(..., ge=0)
    total: int = Field(..., ge=0)
    next_offset: Optional[int] = Field(None, ge=0)
    has_more: bool = Field(False)


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


class LoginResponseEnvelope(BaseModel):
    """Login response wrapped with standard envelope metadata"""
    access_token: str = Field(...)
    token_type: str = Field(...)
    role: str = Field(...)
    message: MessageMeta = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIs...",
                "token_type": "bearer",
                "role": "student",
                "message": {
                    "message_id": "MSG-1000",
                    "level": "INFO",
                    "user_text": "Login successful"
                }
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
    pagination: Optional[PaginationMeta] = Field(None)

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


class SessionListResponseEnvelope(BaseModel):
    """Session list response wrapped with standard envelope metadata"""
    sessions: List[SessionInfo] = Field(...)
    pagination: Optional[PaginationMeta] = Field(None)
    message: MessageMeta = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sessions": [
                    {
                        "id": "uuid-1",
                        "title": "Biology - Chapter 5",
                        "last_updated": "2024-01-15T10:30:00"
                    }
                ],
                "message": {
                    "message_id": "MSG-1000",
                    "level": "INFO",
                    "user_text": "Sessions retrieved successfully"
                }
            }
        }
    )


class SessionContentResponse(BaseModel):
    """Session content response"""
    session_content: Optional[str] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={"example": {"session_content": "/knowledge_base/Class-10/Biology/Chapter-5/notes.pdf"}}
    )


class SessionContentResponseEnvelope(BaseModel):
    """Session content response wrapped with standard envelope metadata"""
    session_content: Optional[str] = Field(None)
    message: MessageMeta = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_content": "/knowledge_base/Class-10/Biology/Chapter-5/notes.pdf",
                "message": {
                    "message_id": "MSG-1000",
                    "level": "INFO",
                    "user_text": "Content retrieved successfully"
                }
            }
        }
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
    bullets: List[str] = Field(default_factory=list)
    numbered: List[str] = Field(default_factory=list)
    status: Optional[str] = Field(None)
    type: Optional[str] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "step_id": 1,
                "title": "Introduction to Photosynthesis",
                "content": "Photosynthesis is...",
                "bullets": ["Plants use sunlight to make food."],
                "numbered": [],
                "status": "not_started",
                "type": "concept"
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


class LessonPlanResponseEnvelope(BaseModel):
    """Lesson plan response wrapped with standard envelope metadata"""
    session_id: str = Field(...)
    chapter: str = Field(...)
    steps: List[LessonStep] = Field(...)
    current_step: Optional[int] = Field(None)
    message: MessageMeta = Field(...)

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
                "current_step": 0,
                "message": {
                    "message_id": "MSG-1000",
                    "level": "INFO",
                    "user_text": "Operation completed successfully."
                }
            }
        }
    )


class FileTreeItem(BaseModel):
    """File tree item"""
    class_name: Optional[str] = Field(None)
    subject: Optional[str] = Field(None)
    folder: Optional[str] = Field(None)
    file_id: Optional[int] = Field(None)
    display_name: Optional[str] = Field(None)
    upload_status: Optional[str] = Field(None)
    index_status: Optional[str] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "class_name": "Class 10",
                "subject": "Biology",
                "folder": "Chapter 5",
                "file_id": 123,
                "display_name": "Photosynthesis Notes",
                "upload_status": "completed",
                "index_status": "indexed"
            }
        }
    )


class FileTreeResponse(BaseModel):
    """Knowledge base file tree response"""
    items: List[FileTreeItem] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "class_name": "Class 10",
                        "subject": "Biology",
                        "folder": "Chapter 5",
                        "file_id": 123,
                        "display_name": "Notes",
                        "upload_status": "completed",
                        "index_status": "indexed"
                    }
                ]
            }
        }
    )


class IndexStatusItem(BaseModel):
    """Index status for a file"""
    file_id: int = Field(...)
    display_name: str = Field(...)
    upload_status: str = Field(...)
    index_status: str = Field(...)
    error_message: Optional[str] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_id": 123,
                "display_name": "Notes.pdf",
                "upload_status": "completed",
                "index_status": "indexed",
                "error_message": None
            }
        }
    )


class IndexStatusResponse(BaseModel):
    """Index status response"""
    items: List[IndexStatusItem] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "file_id": 123,
                        "display_name": "Notes.pdf",
                        "upload_status": "completed",
                        "index_status": "indexed",
                        "error_message": None
                    }
                ]
            }
        }
    )


class ContentsItem(BaseModel):
    """Content item in knowledge base"""
    title: Optional[str] = Field(None)
    content_id: Optional[str] = Field(None)
    path: Optional[str] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Chapter 5 Notes",
                "content_id": "kb:some-path",
                "path": "Class 9/Mathematics/Text Books/notes.pdf"
            }
        }
    )


class ContentsResponse(BaseModel):
    """Contents response"""
    contents: List[ContentsItem] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contents": [
                    {
                        "title": "Chapter 5 Notes",
                        "content_id": "kb:Class 9/Mathematics/Text Books/notes.pdf",
                        "path": "Class 9/Mathematics/Text Books/notes.pdf"
                    }
                ]
            }
        }
    )


class ClassListResponse(BaseModel):
    """Classes list response"""
    classes: List[str] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "classes": ["Class 8", "Class 9", "Class 10"]
            }
        }
    )


class SubjectsResponse(BaseModel):
    """Subjects response"""
    subjects: List[str] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subjects": ["Biology", "Chemistry", "Physics"]
            }
        }
    )


class FoldersResponse(BaseModel):
    """Folders response"""
    folders: List[str] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "folders": ["Chapter 1", "Chapter 2", "Notes"]
            }
        }
    )


class ProfileResponse(BaseModel):
    """User profile response"""
    username: str = Field(...)
    email: str = Field(...)
    role: str = Field(...)
    full_name: Optional[str] = Field(None)
    class_name: Optional[str] = Field(None)
    created_at: Optional[str] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "john_student",
                "email": "john@example.com",
                "role": "student",
                "full_name": "John Doe",
                "class_name": "Class 10",
                "created_at": "2024-01-01T00:00:00"
            }
        }
    )


class ProfileResponseEnvelope(BaseModel):
    """User profile response wrapped with standard envelope metadata"""
    username: str = Field(...)
    email: str = Field(...)
    role: str = Field(...)
    full_name: Optional[str] = Field(None)
    class_name: Optional[str] = Field(None)
    created_at: Optional[str] = Field(None)
    message: MessageMeta = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "john_student",
                "email": "john@example.com",
                "role": "student",
                "full_name": "John Doe",
                "class_name": "Class 10",
                "created_at": "2024-01-01T00:00:00",
                "message": {
                    "message_id": "MSG-1000",
                    "level": "INFO",
                    "user_text": "Profile retrieved successfully"
                }
            }
        }
    )


class PlanSummary(BaseModel):
    """Plan summary (subscription/quota)"""
    plan_id: Optional[str] = Field(None)
    plan_name: str = Field(...)
    total_quota: int = Field(...)
    used_quota: int = Field(...)
    remaining_quota: int = Field(...)
    reset_date: Optional[str] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "plan_id": "plan-free",
                "plan_name": "Free",
                "total_quota": 200,
                "used_quota": 45,
                "remaining_quota": 155,
                "reset_date": "2026-06-01"
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


class PreferencesResponse(BaseModel):
    """User preferences response"""
    preferred_language: str = Field(..., description="ISO 639-1 language code")
    reminder_settings: Optional[Dict[str, Any]] = Field(None, description="Reminder configuration")
    updated: Optional[bool] = Field(None, description="Whether preferences were updated")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "preferred_language": "en",
                "reminder_settings": {
                    "enabled": True,
                    "frequency": "daily",
                    "muted_ids": []
                }
            }
        }
    )


class RelationshipStudentsResponse(BaseModel):
    """Students in relationship response"""
    students: List[Dict[str, Any]] = Field(default_factory=list, description="List of related students")
    status: Optional[str] = Field(None, description="Relationship operation status")
    student_username: Optional[str] = Field(None, description="Linked or unlinked student username")
    student_email: Optional[str] = Field(None, description="Linked student email")
    relation_role: Optional[str] = Field(None, description="Relationship role")
    relation_label: Optional[str] = Field(None, description="Optional relationship label")
    linking_mode: Optional[str] = Field(None, description="How the relationship was created")
    approval_required: Optional[bool] = Field(None, description="Whether student approval is required")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "students": [
                    {"username": "student1", "email": "student1@example.com", "relation_role": "teacher"}
                ]
            }
        }
    )


class RelationshipMentorsResponse(BaseModel):
    """Mentors in relationship response"""
    mentors: List[Dict[str, Any]] = Field(default_factory=list, description="List of mentor relationships")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mentors": [
                    {"username": "mentor1", "email": "mentor@example.com", "relation_role": "teacher"}
                ]
            }
        }
    )


class CollaborationNoteResponse(BaseModel):
    """Collaboration note response"""
    status: Optional[str] = Field(None, description="Operation status")
    note: Optional[Dict[str, Any]] = Field(None, description="Note data")
    note_id: Optional[int] = Field(None, description="Note identifier")
    visibility: Optional[str] = Field(None, description="Note visibility level")
    student_username: Optional[str] = Field(None, description="Associated student username")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "saved",
                "note": {"id": 1, "title": "Note Title", "content": "Note content"},
                "note_id": 1
            }
        }
    )


class CollaborationNotesListResponse(BaseModel):
    """Collaboration notes list response"""
    notes: List[Dict[str, Any]] = Field(default_factory=list, description="List of notes")
    student_username: Optional[str] = Field(None, description="Associated student username")
    pagination: Optional[PaginationMeta] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "notes": [
                    {"id": 1, "title": "Note 1", "content": "Content 1"},
                    {"id": 2, "title": "Note 2", "content": "Content 2"}
                ],
                "student_username": "student123"
            }
        }
    )


class AssignmentResponse(BaseModel):
    """Assignment response"""
    status: Optional[str] = Field(None, description="Operation status")
    assignment_id: Optional[int] = Field(None, description="Assignment identifier")
    student_username: Optional[str] = Field(None, description="Associated student username")
    assignment: Optional[Dict[str, Any]] = Field(None, description="Assignment data")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "created",
                "assignment_id": 1,
                "student_username": "student123"
            }
        }
    )


class AssignmentsListResponse(BaseModel):
    """Assignments list response"""
    assignments: List[Dict[str, Any]] = Field(default_factory=list, description="List of assignments")
    student_username: Optional[str] = Field(None, description="Associated student username")
    pagination: Optional[PaginationMeta] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "assignments": [
                    {"id": 1, "title": "Assignment 1", "due": "2024-12-31"},
                    {"id": 2, "title": "Assignment 2", "due": "2025-01-15"}
                ],
                "student_username": "student123"
            }
        }
    )


class StudentProgressResponse(BaseModel):
    """Student progress response"""
    student_username: str = Field(..., description="Student username")
    dashboard: Optional[Dict[str, Any]] = Field(None, description="Progress dashboard data")
    mastery: Optional[Dict[str, Any]] = Field(None, description="Mastery tracking data")
    insights: Optional[Dict[str, Any]] = Field(None, description="AI-generated insights")
    study_plan: Optional[Dict[str, Any]] = Field(None, description="Study plan data")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_username": "student123",
                "dashboard": {"total_study_seconds": 3600},
                "mastery": {"subjects": []},
                "insights": {"headlines": []},
                "study_plan": {"targets": []}
            }
        }
    )


class ProgressDashboardResponse(BaseModel):
    """Progress dashboard response"""
    total_study_seconds: int = Field(default=0)
    streak_days: int = Field(default=0)
    assessment_scores: Optional[List[int]] = Field(None)
    assignments: Optional[List[Dict[str, Any]]] = Field(None)
    top_subjects: Optional[List[Dict[str, Any]]] = Field(None)
    recent_activity: Optional[List[Dict[str, Any]]] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_study_seconds": 3600,
                "streak_days": 7,
                "assessment_scores": [75, 80, 85],
                "assignments": [],
                "top_subjects": [],
                "recent_activity": []
            }
        }
    )


class ProgressMasteryResponse(BaseModel):
    """Progress mastery response"""
    mastery: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mastery": [
                    {
                        "subject": "Biology",
                        "chapter": "Chapter 5",
                        "mastery_pct": 85
                    }
                ]
            }
        }
    )


class ProgressInsightsResponse(BaseModel):
    """Progress insights response"""
    headlines: Optional[List[str]] = Field(None)
    notifications: Optional[List[Dict[str, Any]]] = Field(None)
    recommendations: Optional[List[Dict[str, Any]]] = Field(None)
    badges: Optional[List[Dict[str, Any]]] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "headlines": ["Great progress this week!"],
                "notifications": [],
                "recommendations": [],
                "badges": []
            }
        }
    )


class ProgressStudyPlanResponse(BaseModel):
    """Progress study plan response"""
    goal_summary: Optional[str] = Field(None)
    targets: Optional[List[Dict[str, Any]]] = Field(None)
    schedule: Optional[List[Dict[str, Any]]] = Field(None)
    history: Optional[Dict[str, Any]] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "goal_summary": "Stay on track with daily goals",
                "targets": [],
                "schedule": [],
                "history": {}
            }
        }
    )


class ActivityLogResponse(BaseModel):
    """Activity log response"""
    logged: bool = Field(...)
    activity_id: Optional[str] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "logged": True,
                "activity_id": "activity-123"
            }
        }
    )


class PlanResponse(BaseModel):
    plan: Dict[str, Any] = Field(...)
    usage: Dict[str, Any] = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "plan": {
                    "user_id": "testuser",
                    "plan_code": "free",
                    "entitlements": [{"feature_key": "basic_lessons", "enabled": True}]
                },
                "usage": {
                    "questions_used": 5,
                    "questions_limit": 10
                }
            }
        }
    )


class PlanResponseEnvelope(PlanResponse):
    """Plan response wrapped with standard envelope metadata"""
    message: MessageMeta = Field(...)

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "plan_name": "Premium",
                "expires_at": "2025-12-31T23:59:59Z",
                "features": ["unlimited_questions", "priority_support", "class_collaboration"],
                "message": {
                    "message_id": "MSG-1000",
                    "level": "INFO",
                    "user_text": "Operation completed successfully."
                }
            }
        }
    )


class PlanLimitsResponse(BaseModel):
    max_students: int = Field(...)
    active_assignments: int = Field(...)
    storage_gb: float = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "max_students": 50,
                "active_assignments": 20,
                "storage_gb": 5.0
            }
        }
    )


class PlanLimitsResponseEnvelope(PlanLimitsResponse):
    """Plan limits response wrapped with standard envelope metadata"""
    message: MessageMeta = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "max_students": 50,
                "active_assignments": 20,
                "storage_gb": 5.0,
                "message": {
                    "message_id": "MSG-1000",
                    "level": "INFO",
                    "user_text": "Operation completed successfully."
                }
            }
        }
    )


class SubscriptionCatalogResponse(BaseModel):
    class_rates: List[Dict[str, Any]] = Field(...)
    plans: Dict[str, Dict[str, Any]] = Field(...)
    promo_codes_supported: bool = Field(...)
    billing_period: str = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "class_rates": [
                    {
                        "class_name": "Class 8",
                        "annual_price_cents": 4999,
                        "currency": "INR"
                    }
                ],
                "plans": {
                    "free": {"entitlements": [{"feature_key": "basic_lessons", "enabled": True}]},
                    "pro": {"entitlements": [{"feature_key": "advanced_analytics", "enabled": True}]}
                },
                "promo_codes_supported": True,
                "billing_period": "annual"
            }
        }
    )


class SubscriptionCatalogResponseEnvelope(SubscriptionCatalogResponse):
    """Subscription catalog response wrapped with standard envelope metadata"""
    message: MessageMeta = Field(...)

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "class_rates": [
                    {
                        "class_name": "Class 8",
                        "annual_price_cents": 4999,
                        "currency": "INR"
                    }
                ],
                "plans": {
                    "free": {"entitlements": [{"feature_key": "basic_lessons", "enabled": True}]},
                    "pro": {"entitlements": [{"feature_key": "advanced_analytics", "enabled": True}]}
                },
                "promo_codes_supported": True,
                "billing_period": "annual",
                "message": {
                    "message_id": "MSG-1000",
                    "level": "INFO",
                    "user_text": "Operation completed successfully."
                }
            }
        }
    )


class SubscriptionQuoteResponse(BaseModel):
    quote_id: str = Field(...)
    amount: float = Field(...)
    currency: str = Field(...)
    valid_until: str = Field(...)

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "quote_id": "Q-12345",
                "amount": 49.99,
                "currency": "USD",
                "valid_until": "2025-01-31T23:59:59Z"
            }
        }
    )


class SubscriptionQuoteResponseEnvelope(SubscriptionQuoteResponse):
    """Subscription quote response wrapped with standard envelope metadata"""
    message: MessageMeta = Field(...)

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "quote_id": "Q-12345",
                "amount": 49.99,
                "currency": "USD",
                "valid_until": "2025-01-31T23:59:59Z",
                "message": {
                    "message_id": "MSG-1000",
                    "level": "INFO",
                    "user_text": "Operation completed successfully."
                }
            }
        }
    )


class SubscriptionActivateResponse(BaseModel):
    subscription_id: Optional[str] = Field(None)
    status: Optional[str] = Field(None)
    activated_at: Optional[str] = Field(None)
    expires_at: Optional[str] = Field(None)
    auto_renew: Optional[bool] = Field(None)
    active_classes: Optional[List[Dict[str, Any]]] = Field(None)
    payment_reference: Optional[str] = Field(None, description="Reference used to confirm activation")
    activation_mode: str = Field("manual", description="Mode used to activate the subscription")

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "status": "active",
                "activated_at": "2025-01-01T12:00:00Z",
                "expires_at": "2026-01-01T12:00:00Z",
                "active_classes": [{"class_name": "Class 8", "auto_renew": True}],
                "payment_reference": "txn-12345",
                "activation_mode": "manual"
            }
        }
    )


class SubscriptionActivateResponseEnvelope(SubscriptionActivateResponse):
    """Subscription activation response wrapped with standard envelope metadata"""
    message: MessageMeta = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subscription_id": "S-67890",
                "status": "active",
                "activated_at": "2025-01-01T12:00:00Z",
                "message": {
                    "message_id": "MSG-1000",
                    "level": "INFO",
                    "user_text": "Operation completed successfully."
                }
            }
        }
    )
