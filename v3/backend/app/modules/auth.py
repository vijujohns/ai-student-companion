"""
JWT Authentication & RBAC module
"""

from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
import os
from fastapi import Response
from dotenv import load_dotenv
from .user_manager import verify_password, get_user_by_identifier
from .db import get_connection
from ..core.debug_logger import dlog, derror

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
TOKEN_COOKIE_NAME = os.getenv("TOKEN_COOKIE_NAME", "access_token")


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


AUTH_COOKIE_SECURE = _env_flag(
    "AUTH_COOKIE_SECURE",
    APP_ENV not in {"development", "dev", "test", "local"},
)
AUTH_COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "lax").strip().lower()
if AUTH_COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    AUTH_COOKIE_SAMESITE = "lax"


def _ensure_secret_is_safe() -> None:
    """Disallow insecure fallback secret outside local/dev environments."""
    if SECRET_KEY != "change-me-in-production":
        return
    if APP_ENV in {"development", "dev", "test", "local"}:
        return
    raise RuntimeError("Unsafe JWT SECRET_KEY configured for non-development environment")


def create_access_token(data: dict):
    """
    Generate JWT token
    """
    _ensure_secret_is_safe()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    dlog("AUTH", "Token created",
         user=data.get("username", "?"),
         role=data.get("role", "?"),
         expires_in_minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
         algorithm=ALGORITHM)
    return token


def authenticate_user(identifier: str, password: str):
    """
    Validate user credentials against database.
    Identifier is email (new flow) with username fallback for legacy users.
    """
    # Mask email for logs: show "u***@domain.com"
    _masked = identifier[:2] + "***" + identifier[identifier.find("@"):] if "@" in identifier else identifier[:2] + "***"
    dlog("AUTH", "Login attempt", identifier=_masked)
    try:
        conn = get_connection()
        try:
            user = get_user_by_identifier(conn, identifier)
        finally:
            conn.close()

        if not user:
            dlog("AUTH", "Login FAILED — user not found", identifier=_masked)
            return None

        password_hash = user.get('password_hash')
        role = user.get('role')

        if not verify_password(password, password_hash):
            dlog("AUTH", "Login FAILED — wrong password", identifier=_masked)
            return None

        if not user.get("is_active"):
            dlog("AUTH", "Login FAILED — account inactive", identifier=_masked)
            return None

        dlog("AUTH", "Login SUCCESS", identifier=_masked, role=role,
             username=user["username"])
        return {
            "username": user["username"],
            "email": user.get("email") or user["username"],
            "role": role,
        }
    except Exception as e:
        derror("AUTH", f"Authentication error: {e}", identifier=_masked)
        return None


def verify_token(token: str):
    """
    Decode and validate JWT token
    """
    try:
        _ensure_secret_is_safe()
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        dlog("AUTH", "Token verified",
             user=payload.get("username", payload.get("sub", "?")),
             role=payload.get("role", "?"))
        return payload
    except JWTError as e:
        dlog("AUTH", "Token verification FAILED", reason=str(e))
        return None


def set_auth_cookie(response: Response, token: str) -> None:
    """Set the HttpOnly auth cookie used by cookie-first session flows."""
    max_age = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(
        key=TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        max_age=max_age,
        expires=max_age,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    """Remove the auth cookie while leaving other local browser state untouched."""
    response.delete_cookie(TOKEN_COOKIE_NAME, path="/")
