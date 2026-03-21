"""
Handles JWT authentication and RBAC
"""

from datetime import datetime, timedelta
import jwt

SECRET = "SECRET_KEY"

def create_token(user_id, role):
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=10)
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def verify_token(token):
    return jwt.decode(token, SECRET, algorithms=["HS256"])