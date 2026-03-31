"""
Auth dependencies for protected routes
"""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .auth import TOKEN_COOKIE_NAME, verify_token
from .policy import check_quota
from .messages import get_message
from ..core.debug_logger import dlog, dwarn

security = HTTPBearer(auto_error=False)  # 🔹 do NOT auto-throw 403

def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Returns the user payload from JWT token
    """
    dlog("AUTH", "get_current_user",
         path=request.url.path,
         method=request.method,
         has_credentials=credentials is not None,
         has_cookie=TOKEN_COOKIE_NAME in request.cookies)

    token = credentials.credentials if credentials else request.cookies.get(TOKEN_COOKIE_NAME)

    if not token:
        dwarn("AUTH", "Authorization header missing", path=request.url.path)
        raise HTTPException(status_code=401, detail="Authorization header missing")

    payload = verify_token(token)

    if not payload:
        dwarn("AUTH", "Token invalid or expired", path=request.url.path)
        raise HTTPException(status_code=401, detail="Invalid token")

    dlog("AUTH", "User authenticated",
         user=payload.get("username", "?"),
         role=payload.get("role", "?"),
         path=request.url.path)
    return payload


def require_role(role: str):
    """
    Role-based access decorator
    """

    def role_checker(user=Depends(get_current_user)):
        dlog("AUTH", "Role check",
             required=role,
             user=user.get("username", "?"),
             user_role=user.get("role", "?"))
        if user["role"] != role:
            dwarn("AUTH", "Access denied — insufficient role",
                  required=role,
                  user=user.get("username", "?"),
                  user_role=user.get("role", "?"))
            raise HTTPException(status_code=403, detail="Access denied")

        return user

    return role_checker


def require_quota(action: str):
    """Plan-aware quota guard for action endpoints."""

    def quota_checker(user=Depends(get_current_user)):
        allowed, message_id = check_quota(user.get("username", ""), action)
        if not allowed:
            msg = get_message(message_id)
            raise HTTPException(
                status_code=429,
                detail={
                    "message_id": msg["message_id"],
                    "level": msg["level"],
                    "message": msg["user_text"],
                },
            )
        return user

    return quota_checker


# ✅ NEW: Session Ownership Validation
def validate_session_ownership(session_id: str, user=Depends(get_current_user)):
    """
    Verify that the user owns the requested session.
    Prevents users from accessing other users' sessions.
    
    Returns: user dict if valid, raises HTTPException if unauthorized
    """
    from .db import get_connection

    dlog("AUTH", "Session ownership check",
         session_id=session_id,
         user=user.get("username", "?"))

    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if session exists and belongs to user
    cursor.execute(
        "SELECT user_id FROM chat_history WHERE session_id = ? LIMIT 1",
        (session_id,)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not result:
        dwarn("AUTH", "Session not found", session_id=session_id,
              user=user.get("username", "?"))
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_owner = result[0]
    requested_by = user["username"]
    
    if session_owner != requested_by:
        dwarn("AUTH", "Session ownership denied",
              session_id=session_id,
              owner=session_owner,
              requested_by=requested_by)
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this session"
        )
    
    dlog("AUTH", "Session ownership verified",
         session_id=session_id, user=requested_by)
    return user
