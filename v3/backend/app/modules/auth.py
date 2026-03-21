"""
JWT Authentication & RBAC module
"""

from datetime import datetime, timedelta
from jose import jwt, JWTError

SECRET_KEY = "super-secret-key"  # 🔥 move to env later
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


# Dummy user store (replace later with DB)
USERS = {
    "student": {"password": "student123", "role": "student"},
    "admin": {"password": "admin123", "role": "admin"},
}


def create_access_token(data: dict):
    """
    Generate JWT token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def authenticate_user(username: str, password: str):
    """
    Validate user credentials
    """
    user = USERS.get(username)
    if not user or user["password"] != password:
        return None

    return {"username": username, "role": user["role"]}


def verify_token(token: str):
    """
    Decode and validate JWT token
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None