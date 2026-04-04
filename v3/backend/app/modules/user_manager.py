"""
User management and password hashing
"""

import hashlib
import os
import sqlite3
import json
from dotenv import load_dotenv

load_dotenv()


def hash_password(password: str) -> str:
    """Hash a plain text password using PBKDF2-SHA256 (built-in, no dependencies)"""
    salt = os.urandom(32)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    # Store salt + hash together (salt:hash format)
    return f"{salt.hex()}:{pwd_hash.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against its hash using constant-time comparison"""
    import hmac
    try:
        salt_hex, hash_hex = hashed_password.split(':')
        salt = bytes.fromhex(salt_hex)
        stored_hash = bytes.fromhex(hash_hex)

        pwd_hash = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt, 100000)
        # Use hmac.compare_digest to prevent timing attacks
        return hmac.compare_digest(pwd_hash, stored_hash)
    except Exception:
        return False


def init_default_users(db_connection):
    """
    Initialize default users on first run.
    This is a one-time setup function that should be called during DB initialization.
    
    Default credentials (CHANGE THESE IN PRODUCTION):
    - student / student123 (role: student)
    - admin / admin123 (role: admin)
    
    For production, use environment variables to set credentials or 
    implement a user registration system.
    """
    cursor = db_connection.cursor()

    app_env = os.getenv("APP_ENV", "development").strip().lower()
    enable_default_users = os.getenv("ENABLE_DEFAULT_USERS", "").strip().lower()
    if enable_default_users not in {"1", "true", "yes"} and app_env in {"production", "prod", "staging"}:
        return
    
    try:
        # Ensure defaults exist (for fresh DBs) and backfill profile/email fields
        # for migrated DBs where legacy rows may not have the new columns populated.
        student_hash = hash_password("student123")
        admin_hash = hash_password("admin123")

        cursor.execute(
            """
            INSERT OR IGNORE INTO users (username, email, first_name, last_name, dob, password_hash, role, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("student", "student@example.com", "Student", "User", "2000-01-01", student_hash, "student", True),
        )
        cursor.execute(
            """
            INSERT OR IGNORE INTO users (username, email, first_name, last_name, dob, password_hash, role, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("admin", "admin@example.com", "Admin", "User", "1990-01-01", admin_hash, "admin", True),
        )

        cursor.execute(
            """
            UPDATE users
            SET
                email = CASE WHEN email IS NULL OR TRIM(email) = '' THEN ? ELSE email END,
                first_name = CASE WHEN first_name IS NULL OR TRIM(first_name) = '' THEN ? ELSE first_name END,
                last_name = CASE WHEN last_name IS NULL OR TRIM(last_name) = '' THEN ? ELSE last_name END,
                dob = CASE WHEN dob IS NULL OR TRIM(dob) = '' THEN ? ELSE dob END
            WHERE username = ?
            """,
            ("student@example.com", "Student", "User", "2000-01-01", "student"),
        )
        cursor.execute(
            """
            UPDATE users
            SET
                email = CASE WHEN email IS NULL OR TRIM(email) = '' THEN ? ELSE email END,
                first_name = CASE WHEN first_name IS NULL OR TRIM(first_name) = '' THEN ? ELSE first_name END,
                last_name = CASE WHEN last_name IS NULL OR TRIM(last_name) = '' THEN ? ELSE last_name END,
                dob = CASE WHEN dob IS NULL OR TRIM(dob) = '' THEN ? ELSE dob END
            WHERE username = ?
            """,
            ("admin@example.com", "Admin", "User", "1990-01-01", "admin"),
        )

        # In local/test environments, keep the seeded default credentials and
        # quota state deterministic so auth and quota-bound API smoke tests stay
        # stable across repeated runs against the persistent app DB.
        if app_env in {"development", "dev", "test", "local"}:
            cursor.execute(
                "UPDATE users SET password_hash=?, is_active=1 WHERE username=?",
                (student_hash, "student"),
            )
            cursor.execute(
                "UPDATE users SET password_hash=?, is_active=1 WHERE username=?",
                (admin_hash, "admin"),
            )
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='usage_counters'"
            )
            if cursor.fetchone():
                cursor.execute(
                    "DELETE FROM usage_counters WHERE user_id IN (?, ?)",
                    ("student", "admin"),
                )

        db_connection.commit()

    except Exception as e:
        print(f"❌ Error initializing users: {e}")
        raise


def get_user_by_username(db_connection, username: str):
    """Fetch user from database by username"""
    cursor = db_connection.cursor()
    cursor.execute("""
        SELECT username, email, first_name, last_name, dob, password_hash, role, is_active
        FROM users
        WHERE username = ?
    """, (username,))
    
    row = cursor.fetchone()
    if row:
        return {
            "username": row[0],
            "email": row[1],
            "first_name": row[2],
            "last_name": row[3],
            "dob": row[4],
            "password_hash": row[5],
            "role": row[6],
            "is_active": row[7]
        }
    return None


def get_user_by_email(db_connection, email: str):
    """Fetch user from database by email."""
    cursor = db_connection.cursor()
    cursor.execute(
        """
        SELECT username, email, first_name, last_name, dob, password_hash, role, is_active
        FROM users
        WHERE email = ?
        """,
        (email,)
    )
    row = cursor.fetchone()
    if row:
        return {
            "username": row[0],
            "email": row[1],
            "first_name": row[2],
            "last_name": row[3],
            "dob": row[4],
            "password_hash": row[5],
            "role": row[6],
            "is_active": row[7],
        }
    return None


def get_user_by_identifier(db_connection, identifier: str):
    """
    Lookup by email first (new flow), then username (legacy compatibility).
    """
    user = get_user_by_email(db_connection, identifier)
    if user:
        return user
    return get_user_by_username(db_connection, identifier)


def register_user(
    db_connection,
    first_name: str,
    last_name: str,
    email: str,
    dob: str,
    password: str,
    role: str = "student",
):
    """Register a new user account. Email acts as unique user ID."""
    cursor = db_connection.cursor()

    existing = get_user_by_email(db_connection, email)
    if existing:
        raise ValueError("Email already registered")

    password_hash = hash_password(password)
    # Keep username aligned to email so downstream code that reads username remains valid.
    username = email

    try:
        cursor.execute(
            """
            INSERT INTO users (username, email, first_name, last_name, dob, password_hash, role, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (username, email, first_name, last_name, dob, password_hash, role, True),
        )
        db_connection.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError("Email already registered") from exc

    return {
        "username": username,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "dob": dob,
        "role": role,
    }


def reset_password_with_email_dob(db_connection, email: str, dob: str, new_password: str):
    """Reset password only when email + DOB match."""
    cursor = db_connection.cursor()
    user = get_user_by_email(db_connection, email)
    if not user:
        return False

    # Normalize date comparison as plain YYYY-MM-DD string.
    if (user.get("dob") or "").strip() != (dob or "").strip():
        return False

    password_hash = hash_password(new_password)
    cursor.execute(
        "UPDATE users SET password_hash=? WHERE email=?",
        (password_hash, email),
    )
    db_connection.commit()
    return cursor.rowcount > 0


def update_user_profile(
    db_connection,
    username: str,
    first_name: str | None = None,
    last_name: str | None = None,
    dob: str | None = None,
    email: str | None = None,
):
    """Update mutable user profile fields and reject email changes."""
    cursor = db_connection.cursor()
    cursor.execute(
        """
        SELECT username, email, first_name, last_name, dob
        FROM users
        WHERE username=?
        LIMIT 1
        """,
        (username,),
    )
    row = cursor.fetchone()
    if not row:
        raise ValueError("User not found")

    current = {
        "username": row[0],
        "email": row[1],
        "first_name": row[2],
        "last_name": row[3],
        "dob": row[4],
    }

    if email is not None and email.strip() and email.strip().lower() != (current.get("email") or "").strip().lower():
        raise ValueError("Email cannot be changed")

    updated = {
        "first_name": first_name if first_name is not None else current.get("first_name"),
        "last_name": last_name if last_name is not None else current.get("last_name"),
        "dob": dob if dob is not None else current.get("dob"),
        "email": current.get("email"),
    }

    cursor.execute(
        """
        UPDATE users
        SET first_name=?, last_name=?, dob=?
        WHERE username=?
        """,
        (updated["first_name"], updated["last_name"], updated["dob"], username),
    )

    changes = {}
    for field in ("first_name", "last_name", "dob"):
        if (current.get(field) or "") != (updated.get(field) or ""):
            changes[field] = {
                "old": current.get(field),
                "new": updated.get(field),
            }

    cursor.execute(
        """
        INSERT INTO profile_audit_log (user_id, action, changes_json)
        VALUES (?, ?, ?)
        """,
        (username, "PROFILE_UPDATE", json.dumps(changes)),
    )

    db_connection.commit()

    return {
        "username": current["username"],
        "email": updated["email"],
        "first_name": updated["first_name"],
        "last_name": updated["last_name"],
        "dob": updated["dob"],
    }
