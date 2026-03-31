"""
Test Session Ownership Validation (Issue #6)
"""

import pytest
from fastapi import HTTPException
from app.modules.dependencies import validate_session_ownership
from app.modules.db import get_connection, init_db
import sqlite3


class TestSessionOwnershipValidation:
    """Test session ownership validation"""
    
    @classmethod
    def setup_class(cls):
        """Setup test database and data"""
        init_db()
        # Add test sessions for different users
        conn = get_connection()
        cursor = conn.cursor()
        
        # Add session for student user
        cursor.execute("""
            INSERT INTO chat_history (user_id, session_id, question, answer, session_title)
            VALUES (?, ?, ?, ?, ?)
        """, ("student", "session-student-1", "Test Q", "Test A", "Student Session"))
        
        # Add session for admin user
        cursor.execute("""
            INSERT INTO chat_history (user_id, session_id, question, answer, session_title)
            VALUES (?, ?, ?, ?, ?)
        """, ("admin", "session-admin-1", "Admin Q", "Admin A", "Admin Session"))
        
        conn.commit()
        conn.close()
    
    def test_validate_session_owned_by_user(self):
        """User should access their own session"""
        user = {"username": "student", "role": "student"}
        session_id = "session-student-1"
        
        # Should not raise exception
        result = validate_session_ownership(session_id, user)
        assert result["username"] == "student"
    
    def test_validate_session_not_owned_by_user(self):
        """User should not access someone else's session"""
        user = {"username": "student", "role": "student"}
        session_id = "session-admin-1"  # Admin's session
        
        # Should raise 403 Forbidden
        with pytest.raises(HTTPException) as exc_info:
            validate_session_ownership(session_id, user)
        
        assert exc_info.value.status_code == 403
        assert "do not have access" in exc_info.value.detail
    
    def test_validate_nonexistent_session(self):
        """Accessing non-existent session should return 404"""
        user = {"username": "student", "role": "student"}
        session_id = "session-nonexistent"
        
        # Should raise 404 Not Found
        with pytest.raises(HTTPException) as exc_info:
            validate_session_ownership(session_id, user)
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
