"""
Auth dependencies for protected routes
"""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.modules.auth import verify_token

security = HTTPBearer(auto_error=False)  # 🔹 do NOT auto-throw 403

def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Returns the user payload from JWT token
    """
    # 🔹 Debug: print incoming headers
    #print("Incoming request headers:", request.headers)

    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    token = credentials.credentials
    payload = verify_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    return payload


def require_role(role: str):
    """
    Role-based access decorator
    """

    def role_checker(user=Depends(get_current_user)):
        if user["role"] != role:
            raise HTTPException(status_code=403, detail="Access denied")

        return user

    return role_checker