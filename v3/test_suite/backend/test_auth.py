"""
Test Authentication & Password Hashing (Issue #2)
"""

import pytest
from app.modules.user_manager import hash_password, verify_password, get_user_by_username, init_default_users
from app.modules.auth import authenticate_user
from app.modules.db import get_connection, init_db
import sqlite3


class TestUnitHashPassword:
    """Unit tests for password hashing"""
    
    def test_hash_password_creates_unique_hashes(self):
        """Same password should produce different hashes (due to salt)"""
        password = "test123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        assert hash1 != hash2, "Hashes should be different due to salt"
        assert ":" in hash1, "Hash format should contain salt:hash"
    
    def test_verify_password_correct(self):
        """Correct password should verify"""
        password = "mypassword123"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) == True
    
    def test_verify_password_incorrect(self):
        """Incorrect password should not verify"""
        password = "correctpassword"
        wrong_password = "wrongpassword"
        hashed = hash_password(password)
        
        assert verify_password(wrong_password, hashed) == False
    
    def test_verify_password_empty(self):
        """Empty password should not verify against non-empty hash"""
        password = "test123"
        hashed = hash_password(password)
        
        assert verify_password("", hashed) == False
    
    def test_verify_password_malformed_hash(self):
        """Malformed hash should not crash"""
        result = verify_password("password", "invalid:hash:format")
        assert result == False


class TestIntegrationAuth:
    """Integration tests for authentication"""
    
    @classmethod
    def setup_class(cls):
        """Setup test database"""
        init_db()
    
    def test_authenticate_user_success(self):
        """Successful authentication with correct credentials"""
        # student:student123 is created by init_default_users
        user = authenticate_user("student", "student123")
        
        assert user is not None
        assert user["username"] == "student"
        assert user["role"] == "student"
    
    def test_authenticate_user_wrong_password(self):
        """Authentication fails with wrong password"""
        user = authenticate_user("student", "wrongpassword")
        
        assert user is None
    
    def test_authenticate_user_nonexistent(self):
        """Authentication fails for non-existent user"""
        user = authenticate_user("nonexistent", "anypassword")
        
        assert user is None
    
    def test_authenticate_admin_user(self):
        """Admin user authentication works"""
        user = authenticate_user("admin", "admin123")
        
        assert user is not None
        assert user["username"] == "admin"
        assert user["role"] == "admin"

    def test_authenticate_inactive_user_rejected(self):
        """Authentication fails for a disabled account even with correct credentials."""
        import sqlite3 as _sqlite3
        from app.modules.user_manager import hash_password as _hp

        # Insert a deactivated user directly into the test DB.
        conn = get_connection()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO users (username, email, password_hash, role, is_active) "
                "VALUES (?, ?, ?, ?, ?)",
                ("inactive_user", "inactive@example.com", _hp("pass123"), "student", 0),
            )
            conn.commit()
        finally:
            conn.close()

        user = authenticate_user("inactive@example.com", "pass123")
        assert user is None, "Inactive account must not be authenticated"


class TestRegisterAndReset:
    """Integration tests for register and reset-password APIs"""

    @classmethod
    def setup_class(cls):
        init_db()

    def test_register_then_login(self):
        from app.modules.user_manager import register_user

        email = "newuser_auth_test@example.com"

        conn = get_connection()
        try:
            register_user(
                conn,
                first_name="New",
                last_name="User",
                email=email,
                dob="2005-05-05",
                password="newPass123",
            )
        except ValueError:
            pass
        finally:
            conn.close()

        user = authenticate_user(email, "newPass123")
        assert user is not None

    def test_reset_password_with_email_and_dob(self):
        from app.modules.user_manager import register_user, reset_password_with_email_dob

        email = "reset_auth_test@example.com"

        conn = get_connection()
        try:
            try:
                register_user(
                    conn,
                    first_name="Reset",
                    last_name="User",
                    email=email,
                    dob="2003-03-03",
                    password="oldPass123",
                )
            except ValueError:
                pass

            assert reset_password_with_email_dob(conn, email, "2003-03-03", "newPass456") is True
        finally:
            conn.close()

        user = authenticate_user(email, "newPass456")
        assert user is not None

    def test_reset_password_rejects_wrong_dob(self):
        from app.modules.user_manager import register_user, reset_password_with_email_dob

        email = "reset_wrong_dob_test@example.com"

        conn = get_connection()
        try:
            try:
                register_user(
                    conn,
                    first_name="Wrong",
                    last_name="Dob",
                    email=email,
                    dob="2001-01-01",
                    password="origPass123",
                )
            except ValueError:
                pass

            assert reset_password_with_email_dob(conn, email, "2000-01-01", "shouldFailPass") is False
        finally:
            conn.close()


class TestDefaultUserBackfill:
    """Regression test for legacy default-user rows missing profile/email fields."""

    def test_init_default_users_backfills_legacy_student_admin_rows(self):
        conn = sqlite3.connect(":memory:")
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE users (
                    username TEXT UNIQUE,
                    email TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    dob TEXT,
                    password_hash TEXT,
                    role TEXT,
                    is_active BOOLEAN
                )
                """
            )

            # Simulate legacy rows where new profile fields were added later.
            cursor.execute(
                """
                INSERT INTO users (username, email, first_name, last_name, dob, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("student", "", None, "", None, hash_password("student123"), "student", True),
            )
            cursor.execute(
                """
                INSERT INTO users (username, email, first_name, last_name, dob, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("admin", None, "", None, "", hash_password("admin123"), "admin", True),
            )
            conn.commit()

            init_default_users(conn)

            student = get_user_by_username(conn, "student")
            admin = get_user_by_username(conn, "admin")

            assert student is not None
            assert student["email"] == "student@example.com"
            assert student["first_name"] == "Student"
            assert student["last_name"] == "User"
            assert student["dob"] == "2000-01-01"

            assert admin is not None
            assert admin["email"] == "admin@example.com"
            assert admin["first_name"] == "Admin"
            assert admin["last_name"] == "User"
            assert admin["dob"] == "1990-01-01"

            cursor.execute("SELECT COUNT(*) FROM users")
            assert cursor.fetchone()[0] == 2
        finally:
            conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
