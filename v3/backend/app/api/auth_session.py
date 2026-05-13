"""Auth, profile, and chat session API router."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from ..modules.db import get_connection
from ..modules.dependencies import get_current_user, validate_session_ownership
from ..modules.messages import envelope
from ..modules.adapters import get_default_service_registry
from ..schemas.request import (
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    ProfileUpdateRequest,
    RenameSessionRequest,
    SetSessionContentRequest,
)
from ..schemas.response import (
    LoginResponseEnvelope,
    ProfileResponseEnvelope,
    SessionListResponseEnvelope,
    SessionContentResponseEnvelope,
)

router = APIRouter()
services = get_default_service_registry()


@router.post("/login", response_model=LoginResponseEnvelope)
def login(request: LoginRequest, response: Response):
    """Validate username and password fields."""
    try:
        payload = services.identity.login(request.email, request.password, response)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    return envelope(payload, message_id="MSG-1000")


@router.get("/auth/session")
def get_auth_session(user=Depends(get_current_user)):
    """Return canonical authenticated user identity for cookie/bootstrap flows."""
    return envelope(services.identity.get_auth_session(user), message_id="MSG-1000")


@router.post("/logout")
def logout(response: Response):
    return envelope(services.identity.logout(response), message_id="MSG-1000")


@router.post("/register")
def register(request: RegisterRequest):
    """Register a new user account. Email is the unique user ID."""
    try:
        result = services.identity.register(
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            dob=request.dob,
            password=request.password,
            role=request.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return envelope(result, message_id="MSG-1000")


@router.get("/profile", response_model=ProfileResponseEnvelope)
def get_profile(user=Depends(get_current_user)):
    """Return the editable profile details for the current user."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT username, email, role, first_name, last_name, dob
            FROM users
            WHERE username = ?
            LIMIT 1
            """,
            (user["username"],),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")

    return envelope(
        {
            "profile": {
                "username": row[0],
                "email": row[1],
                "role": row[2],
                "first_name": row[3],
                "last_name": row[4],
                "dob": row[5],
            }
        },
        message_id="MSG-1000",
    )


@router.put("/profile")
def update_profile(request: ProfileUpdateRequest, user=Depends(get_current_user)):
    """Update mutable profile fields while keeping email immutable."""
    try:
        updated = services.identity.update_profile(
            username=user["username"],
            first_name=request.first_name,
            last_name=request.last_name,
            dob=request.dob,
            email=request.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return envelope({"profile": updated, "status": "updated"}, message_id="MSG-1000")


@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest):
    """Reset password using email + DOB match."""
    ok = services.identity.reset_password(
        email=request.email,
        dob=request.dob,
        new_password=request.new_password,
    )

    if not ok:
        raise HTTPException(status_code=400, detail="Invalid email or DOB")

    return envelope({"status": "password_reset"}, message_id="MSG-1000")


@router.get("/sessions", response_model=SessionListResponseEnvelope)
def get_sessions(
    limit: Optional[int] = Query(None, ge=1, le=100),
    offset: Optional[int] = Query(None, ge=0),
    user=Depends(get_current_user),
):
    """Return sessions with persisted titles."""
    page = services.learning.list_chat_sessions(user["username"], limit=limit, offset=offset)
    return envelope({"sessions": page["items"], "pagination": page["pagination"]}, message_id="MSG-1000")


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, user=Depends(validate_session_ownership)):
    """Persistently delete a session with ownership validation."""
    return envelope(services.learning.delete_chat_session(user["username"], session_id), message_id="MSG-1000")


@router.put("/sessions/{session_id}")
def rename_session(session_id: str, request: RenameSessionRequest, user=Depends(validate_session_ownership)):
    """Persistently rename a session."""
    return envelope(services.learning.rename_chat_session(user["username"], session_id, request.title), message_id="MSG-1000")


@router.get("/sessions/{session_id}/content", response_model=SessionContentResponseEnvelope)
def get_session_content(session_id: str, user=Depends(get_current_user)):
    """Return session content; new sessions are valid and return null content."""
    return envelope(services.learning.get_session_content(user, session_id), message_id="MSG-1000")


@router.put("/sessions/{session_id}/content")
def set_session_content(session_id: str, request: SetSessionContentRequest, user=Depends(get_current_user)):
    """Update session content path (PDF etc.)."""
    return envelope(services.learning.set_session_content(user, session_id, request.content_id), message_id="MSG-1000")
