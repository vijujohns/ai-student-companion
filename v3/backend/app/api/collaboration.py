from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from ..modules.adapters import get_default_service_registry
from ..modules.db import get_connection
from ..modules.dependencies import get_current_user
from ..modules.messages import envelope
from ..modules.notes import (
    delete_note as delete_user_note,
    get_note as get_user_note,
    list_notes as list_user_notes,
    save_note as save_user_note,
    update_note as update_user_note,
)
from ..schemas.request import (
    LinkStudentRequest,
    CollaborationNoteRequest,
    CollaborationNoteUpdateRequest,
    MentorAssignmentRequest,
    MentorAssignmentUpdateRequest,
)
from ..schemas.response import (
    RelationshipStudentsResponse,
    RelationshipMentorsResponse,
    CollaborationNoteResponse,
    CollaborationNotesListResponse,
    AssignmentResponse,
    AssignmentsListResponse,
    StudentProgressResponse,
)

router = APIRouter()
services = get_default_service_registry()


def _get_user_row_by_email(email: str):
    return services.relationships.get_user_by_email(email)


def _resolve_student_user_id(student_identifier: str) -> str | None:
    return services.relationships.resolve_student_user_id(student_identifier)


def _has_relationship_access(student_user_id: str, requester: dict) -> bool:
    return services.relationships.has_relationship_access(student_user_id, requester)


@router.post("/relationships/link-student", response_model=RelationshipStudentsResponse)
def link_student(request: LinkStudentRequest, user=Depends(get_current_user)):
    requester_role = user.get("role", "student")
    if requester_role not in {"teacher", "parent"}:
        raise HTTPException(status_code=403, detail="Only teacher or parent accounts can link students")

    student = _get_user_row_by_email(request.student_email)
    if not student:
        raise HTTPException(status_code=404, detail="Student account not found")
    if student["role"] != "student":
        raise HTTPException(status_code=400, detail="Target user must have student role")

    services.relationships.link_student(
        student_user_id=student["username"],
        related_user_id=user["username"],
        relation_role=requester_role,
        relation_label=request.relation_label,
    )

    return envelope(
        {
            "status": "linked",
            "student_username": student["username"],
            "student_email": student["email"],
            "relation_role": requester_role,
            "relation_label": request.relation_label,
            "linking_mode": "direct_existing_student",
            "approval_required": False,
        },
        message_id="MSG-1000",
    )


@router.delete("/relationships/students/{student_identifier}")
def unlink_student(student_identifier: str, user=Depends(get_current_user)):
    requester_role = user.get("role", "student")
    if requester_role not in {"teacher", "parent"}:
        raise HTTPException(status_code=403, detail="Only teacher or parent accounts can unlink students")

    student_user_id = _resolve_student_user_id(student_identifier)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")

    deleted = services.relationships.unlink_student(
        student_user_id=student_user_id,
        related_user_id=user["username"],
        relation_role=requester_role,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Relationship not found")

    return envelope(
        {"status": "unlinked", "student_username": student_user_id, "relation_role": requester_role},
        message_id="MSG-1000",
    )


@router.get("/relationships/my-students", response_model=RelationshipStudentsResponse)
def my_students(user=Depends(get_current_user)):
    requester_role = user.get("role", "student")
    if requester_role not in {"teacher", "parent"}:
        raise HTTPException(status_code=403, detail="Only teacher or parent accounts can list linked students")

    students = services.relationships.list_students_for_related(user["username"], requester_role)
    return envelope({"students": students}, message_id="MSG-1000")


@router.get("/relationships/my-mentors", response_model=RelationshipMentorsResponse)
def my_mentors(user=Depends(get_current_user)):
    if user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Only student accounts can list mentors")

    mentors = services.relationships.list_mentors_for_student(user["username"])
    return envelope({"mentors": mentors}, message_id="MSG-1000")


@router.post("/notes/save", response_model=CollaborationNoteResponse)
def save_summary_note(request: CollaborationNoteRequest, user=Depends(get_current_user)):
    note = save_user_note(
        user["username"],
        title=request.title,
        content=request.content,
        session_id=request.session_id,
        source_query=request.source_query,
        selected_content=request.selected_content,
        is_pinned=request.is_pinned,
    )
    return envelope({"status": "saved", "note": note}, message_id="MSG-1000")


@router.get("/notes", response_model=CollaborationNotesListResponse)
def list_summary_notes(
    limit: Optional[int] = Query(None, ge=1, le=100),
    offset: Optional[int] = Query(None, ge=0),
    user=Depends(get_current_user),
):
    from ..modules.pagination import paginate_items
    page = paginate_items(list_user_notes(user["username"]), limit=limit, offset=offset)
    return envelope({"notes": page["items"], "pagination": page["pagination"]}, message_id="MSG-1000")


@router.get("/notes/{note_id}", response_model=CollaborationNoteResponse)
def get_summary_note(note_id: int, user=Depends(get_current_user)):
    note = get_user_note(user["username"], note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return envelope({"note": note}, message_id="MSG-1000")


@router.put("/notes/{note_id}", response_model=CollaborationNoteResponse)
def update_summary_note(note_id: int, request: CollaborationNoteUpdateRequest, user=Depends(get_current_user)):
    note = update_user_note(
        user["username"],
        note_id,
        title=request.title,
        content=request.content,
        source_query=request.source_query,
        selected_content=request.selected_content,
        is_pinned=request.is_pinned,
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return envelope({"status": "updated", "note": note}, message_id="MSG-1000")


@router.delete("/notes/{note_id}")
def delete_summary_note(note_id: int, user=Depends(get_current_user)):
    deleted = delete_user_note(user["username"], note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return envelope({"status": "deleted", "note_id": note_id}, message_id="MSG-1000")


@router.get("/students/{student_username}/progress", response_model=StudentProgressResponse)
def get_student_progress(student_username: str, user=Depends(get_current_user)):
    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")
    dashboard, mastery = services.progress.get_student_progress(student_user_id)
    insights = services.progress.get_insights(student_user_id)
    study_plan = services.progress.get_study_plan(student_user_id)
    return envelope(
        {
            "student_username": student_user_id,
            "dashboard": dashboard,
            "mastery": mastery,
            "insights": insights,
            "study_plan": study_plan,
        },
        message_id="MSG-1000",
    )


@router.post("/collaboration/notes", response_model=CollaborationNoteResponse)
def add_collaboration_note(request: CollaborationNoteRequest, user=Depends(get_current_user)):
    role = user.get("role", "student")
    student_user_id = _resolve_student_user_id(request.student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if role not in {"teacher", "parent", "admin"}:
        raise HTTPException(status_code=403, detail="Only teacher, parent, or admin can add notes")
    if role != "admin" and not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    note_id = services.relationships.create_note(
        student_user_id=student_user_id,
        author_user_id=user["username"],
        author_role=role,
        note_text=request.note_text.strip(),
        visibility=request.visibility,
    )

    return envelope(
        {
            "status": "created",
            "note_id": note_id,
            "student_username": student_user_id,
            "visibility": request.visibility,
        },
        message_id="MSG-1000",
    )


@router.get("/students/{student_username}/notes", response_model=CollaborationNotesListResponse)
def get_collaboration_notes(
    student_username: str,
    limit: Optional[int] = Query(None, ge=1, le=100),
    offset: Optional[int] = Query(None, ge=0),
    user=Depends(get_current_user),
):
    role = user.get("role", "student")
    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    page = services.relationships.list_notes(student_user_id, role, user["username"], limit=limit, offset=offset)
    return envelope({"student_username": student_user_id, "notes": page["items"], "pagination": page["pagination"]}, message_id="MSG-1000")


@router.put("/students/{student_username}/notes/{note_id}", response_model=CollaborationNoteResponse)
def update_collaboration_note(
    student_username: str,
    note_id: int,
    request: CollaborationNoteUpdateRequest,
    user=Depends(get_current_user),
):
    role = user.get("role", "student")
    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if role not in {"teacher", "parent", "admin"}:
        raise HTTPException(status_code=403, detail="Only teacher, parent, or admin can update notes")
    if role != "admin" and not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    updated = services.relationships.update_note(
        student_user_id=student_user_id,
        note_id=note_id,
        updates=request.model_dump(exclude_none=True),
        requester_user_id=user["username"],
        requester_role=role,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Note not found")

    return envelope(updated, message_id="MSG-1000")


@router.delete("/students/{student_username}/notes/{note_id}")
def delete_collaboration_note(student_username: str, note_id: int, user=Depends(get_current_user)):
    role = user.get("role", "student")
    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if role not in {"teacher", "parent", "admin"}:
        raise HTTPException(status_code=403, detail="Only teacher, parent, or admin can delete notes")
    if role != "admin" and not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    deleted = services.relationships.delete_note(
        student_user_id=student_user_id,
        note_id=note_id,
        requester_user_id=user["username"],
        requester_role=role,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")

    return envelope(
        {"status": "deleted", "note_id": note_id, "student_username": student_user_id},
        message_id="MSG-1000",
    )


@router.post("/students/{student_username}/assignments", response_model=AssignmentResponse)
def create_student_assignment(student_username: str, request: MentorAssignmentRequest, user=Depends(get_current_user)):
    role = user.get("role", "student")
    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if role not in {"teacher", "parent", "admin"}:
        raise HTTPException(status_code=403, detail="Only teacher, parent, or admin can assign tasks")
    if role != "admin" and not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    assignment_id = services.relationships.create_assignment(
        student_user_id=student_user_id,
        author_user_id=user["username"],
        author_role=role,
        title=request.title.strip(),
        description=request.description.strip(),
        action_tab=request.action_tab,
        cta_label=(request.cta_label or "Open Assignment").strip(),
        chapter_hint=(request.chapter_hint or "").strip() or None,
        context_hint=(request.context_hint or request.description).strip(),
        due_label=(request.due_label or "").strip() or None,
    )

    return envelope(
        {"status": "created", "assignment_id": assignment_id, "student_username": student_user_id},
        message_id="MSG-1000",
    )


@router.get("/students/{student_username}/assignments", response_model=AssignmentsListResponse)
def get_student_assignments(
    student_username: str,
    limit: Optional[int] = Query(None, ge=1, le=100),
    offset: Optional[int] = Query(None, ge=0),
    user=Depends(get_current_user),
):
    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    page = services.relationships.list_assignments(student_user_id, limit=limit, offset=offset)
    return envelope({"student_username": student_user_id, "assignments": page["items"], "pagination": page["pagination"]}, message_id="MSG-1000")


@router.put("/students/{student_username}/assignments/{assignment_id}", response_model=AssignmentResponse)
def update_student_assignment(
    student_username: str,
    assignment_id: int,
    request: MentorAssignmentUpdateRequest,
    user=Depends(get_current_user),
):
    role = user.get("role", "student")
    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    updates = request.model_dump(exclude_unset=True)
    if role == "student":
        if set(updates.keys()) - {"status"}:
            raise HTTPException(status_code=403, detail="Students can only update assignment status")
    elif role not in {"teacher", "parent", "admin"}:
        raise HTTPException(status_code=403, detail="Only teacher, parent, or admin can update assignments")

    for field in ("title", "description", "chapter_hint", "context_hint"):
        if field in updates and isinstance(updates[field], str):
            updates[field] = updates[field].strip()
    if "cta_label" in updates and isinstance(updates["cta_label"], str):
        updates["cta_label"] = updates["cta_label"].strip() or "Open Assignment"
    if "due_label" in updates and isinstance(updates["due_label"], str):
        updates["due_label"] = updates["due_label"].strip() or None

    updated = services.relationships.update_assignment(student_user_id, assignment_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if role == "student" and updated.get("status") == "completed":
        _log_progress_activity_safe(
            user,
            updated.get("action_tab") or "other",
            subject=updated.get("chapter_hint") or updated.get("title") or "Assignment",
            chapter=updated.get("chapter_hint") or updated.get("title") or "Assignment",
            duration_seconds=300,
        )

    return envelope(updated, message_id="MSG-1000")


@router.delete("/students/{student_username}/assignments/{assignment_id}")
def delete_student_assignment(student_username: str, assignment_id: int, user=Depends(get_current_user)):
    role = user.get("role", "student")
    if role not in {"teacher", "parent", "admin"}:
        raise HTTPException(status_code=403, detail="Only teacher, parent, or admin can delete assignments")

    student_user_id = _resolve_student_user_id(student_username)
    if not student_user_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if role != "admin" and not _has_relationship_access(student_user_id, user):
        raise HTTPException(status_code=403, detail="Access denied for this student")

    deleted = services.relationships.delete_assignment(student_user_id, assignment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Assignment not found")

    return envelope({"status": "deleted", "assignment_id": assignment_id, "student_username": student_user_id}, message_id="MSG-1000")


def _log_progress_activity_safe(
    user: dict,
    activity_type: str,
    *,
    subject: str = "",
    chapter: str = "",
    duration_seconds: int = 0,
) -> None:
    try:
        services.progress.log_activity(
            user_id=user.get("username", ""),
            activity_type=activity_type,
            subject=subject or "",
            chapter=chapter or "",
            duration_seconds=max(0, int(duration_seconds or 0)),
        )
    except Exception:
        pass
