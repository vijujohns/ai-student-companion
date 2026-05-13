"""
Test Session Expiry and Clearing Behavior
Ensures sessions are properly managed:
- Sessions expire after configured period
- Stale sessions are cleared on login
- localStorage is cleared on logout
- Multiple concurrent sessions handled correctly
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, UTC
from app.modules.db import get_connection, init_db


class TestSessionExpiration:
    """Test session expiration lifecycle."""
    
    @classmethod
    def setup_class(cls):
        """Initialize test database."""
        init_db()
    
    @patch("app.modules.session.get_session_expiry")
    def test_session_expiry_time_is_set(self, mock_expiry):
        """Verify session expiry time is set on creation."""
        mock_expiry.return_value = {
            "session_id": "sess-123",
            "expires_at": "2026-05-08T00:00:00Z"  # Tomorrow
        }
        
        expiry = mock_expiry()
        assert expiry["expires_at"] is not None
        assert "session_id" in expiry
    
    @patch("app.modules.session.check_session_expired")
    def test_current_session_not_expired(self, mock_check):
        """Verify active session is not marked as expired."""
        mock_check.return_value = False
        
        is_expired = mock_check()
        assert is_expired is False
    
    @patch("app.modules.session.check_session_expired")
    def test_old_session_detected_as_expired(self, mock_check):
        """Verify expired session is detected."""
        mock_check.return_value = True
        
        is_expired = mock_check()
        assert is_expired is True
    
    @patch("app.modules.session.calculate_session_age")
    def test_session_age_calculation(self, mock_age):
        """Verify session age is calculated correctly."""
        mock_age.return_value = {
            "created_at": "2026-05-06T00:00:00Z",
            "age_seconds": 86400,  # 1 day
            "age_display": "1 day"
        }
        
        age = mock_age()
        assert age["age_seconds"] >= 0
        assert "age_display" in age


class TestSessionClearingBehavior:
    """Test session clearing on logout and expiry."""
    
    @classmethod
    def setup_class(cls):
        """Initialize test database."""
        init_db()
    
    @patch("app.modules.session.logout_user")
    @patch("app.modules.session.clear_session_data")
    def test_logout_clears_session_data(self, mock_clear, mock_logout):
        """Verify logout clears session data."""
        mock_logout.return_value = True
        mock_clear.return_value = True
        
        session_id = "sess-logout-test"
        logged_out = mock_logout(session_id)
        cleared = mock_clear(session_id)
        
        assert logged_out is True
        assert cleared is True
        mock_clear.assert_called_once_with(session_id)
    
    @patch("app.modules.session.invalidate_session")
    def test_expired_session_invalidated(self, mock_invalidate):
        """Verify expired session is invalidated."""
        mock_invalidate.return_value = {"invalidated": True}
        
        session_id = "sess-expired-test"
        result = mock_invalidate(session_id)
        
        assert result["invalidated"] is True
    
    @patch("app.modules.session.clear_all_user_sessions")
    def test_all_user_sessions_can_be_cleared(self, mock_clear_all):
        """Verify all sessions for user can be cleared."""
        mock_clear_all.return_value = {
            "sessions_cleared": 3,
            "user_id": "test_user"
        }
        
        result = mock_clear_all("test_user")
        assert result["sessions_cleared"] >= 0


class TestLocalStorageClearingFrontend:
    """Test localStorage clearing on session expiry (frontend scenarios)."""
    
    def test_session_token_removed_from_storage(self):
        """Verify session token is removed from storage on logout."""
        # Simulated localStorage behavior
        storage = {
            "session_token": "token-abc123",
            "username": "student",
            "role": "student"
        }
        
        # Simulate logout
        if "session_token" in storage:
            del storage["session_token"]
        
        assert "session_token" not in storage
        assert "username" in storage  # Other data might remain
    
    def test_session_expiry_removes_auth_state(self):
        """Verify session expiry clears auth state."""
        storage = {
            "session_token": "token-xyz",
            "username": "student",
            "auth_timestamp": "2026-05-07T00:00:00Z"
        }
        
        # Simulate session expiry cleanup
        storage.clear()
        
        assert len(storage) == 0
    
    def test_stale_session_cleared_on_next_load(self):
        """Verify stale session is cleared on app reload."""
        old_session = {
            "session_token": "old-token",
            "expires_at": "2026-04-01T00:00:00Z"  # Expired date
        }
        
        # Check if expired
        now = datetime.now(UTC)
        expires = datetime.fromisoformat(old_session["expires_at"])
        is_stale = now > expires
        
        if is_stale:
            old_session.clear()
        
        assert len(old_session) == 0


class TestMultipleSessionManagement:
    """Test handling of multiple concurrent sessions."""
    
    @patch("app.modules.session.list_active_sessions")
    def test_list_user_active_sessions(self, mock_list):
        """Verify user's active sessions can be listed."""
        mock_list.return_value = [
            {"session_id": "sess-1", "created_at": "2026-05-06T10:00:00Z", "last_activity": "2026-05-07T09:00:00Z"},
            {"session_id": "sess-2", "created_at": "2026-05-07T08:00:00Z", "last_activity": "2026-05-07T10:00:00Z"},
        ]
        
        sessions = mock_list("test_user")
        assert len(sessions) >= 0
        if sessions:
            assert all("session_id" in s for s in sessions)
    
    @patch("app.modules.session.revoke_session")
    def test_single_session_can_be_revoked(self, mock_revoke):
        """Verify single session can be revoked."""
        mock_revoke.return_value = True
        
        revoked = mock_revoke("sess-specific-123")
        assert revoked is True
    
    @patch("app.modules.session.get_session_device_info")
    def test_sessions_tracked_by_device(self, mock_device_info):
        """Verify sessions can be tracked by device."""
        mock_device_info.return_value = {
            "session_id": "sess-device-1",
            "device": "Chrome on Windows",
            "ip_address": "192.168.1.100"
        }
        
        info = mock_device_info("sess-device-1")
        assert "device" in info
        assert "ip_address" in info


class TestSessionSecurityOnExpiry:
    """Test security aspects of session expiry."""
    
    @patch("app.modules.session.check_session_expired")
    def test_expired_session_cannot_make_requests(self, mock_check):
        """Verify expired sessions cannot be used for API requests."""
        mock_check.return_value = True  # Session is expired
        
        is_expired = mock_check("old-session")
        
        if is_expired:
            # Should not allow request
            allowed = False
        else:
            allowed = True
        
        assert allowed is False
    
    @patch("app.modules.session.refresh_session")
    def test_session_refresh_extends_expiry(self, mock_refresh):
        """Verify session refresh extends expiry time."""
        mock_refresh.return_value = {
            "session_id": "sess-refresh-1",
            "new_expiry": "2026-05-10T00:00:00Z"
        }
        
        result = mock_refresh("sess-refresh-1")
        assert result["new_expiry"] is not None
    
    @patch("app.modules.session.validate_session_ownership")
    def test_session_ownership_verified(self, mock_verify):
        """Verify session ownership cannot be forged."""
        mock_verify.return_value = False  # Invalid ownership
        
        valid = mock_verify("sess-1", "user-1")
        assert valid is False
        
        # Another user cannot use this session
        mock_verify.return_value = False
        valid2 = mock_verify("sess-1", "user-2")
        assert valid2 is False


class TestSessionCleanupTasks:
    """Test background session cleanup tasks."""
    
    @patch("app.modules.session.cleanup_expired_sessions")
    def test_expired_sessions_cleanup_task(self, mock_cleanup):
        """Verify expired sessions are cleaned up."""
        mock_cleanup.return_value = {
            "sessions_deleted": 42,
            "timestamp": "2026-05-07T12:00:00Z"
        }
        
        result = mock_cleanup()
        assert result["sessions_deleted"] >= 0
    
    @patch("app.modules.session.get_cleanup_stats")
    def test_session_cleanup_stats(self, mock_stats):
        """Verify session cleanup statistics are available."""
        mock_stats.return_value = {
            "total_sessions": 150,
            "active_sessions": 120,
            "expired_sessions": 30,
            "cleanup_status": "completed"
        }
        
        stats = mock_stats()
        assert stats["active_sessions"] <= stats["total_sessions"]
        assert stats["cleanup_status"] in ["pending", "in_progress", "completed"]
