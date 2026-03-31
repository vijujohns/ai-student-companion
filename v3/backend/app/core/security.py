"""
Compatibility wrapper for legacy imports.

Use app.modules.auth for all new code.
"""

from ..modules.auth import create_access_token as _create_access_token
from ..modules.auth import verify_token


def create_token(user_id, role):
    """Backward-compatible token factory used by older scripts."""
    return _create_access_token({"username": user_id, "role": role})