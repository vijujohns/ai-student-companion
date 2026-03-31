"""
SQLite DB module for chat history & progress tracking with detailed error handling
"""

import sqlite3
import os
import traceback
import json
from datetime import datetime

# 🔥 Resolve project root dynamically
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
DB_FILE = os.path.join(BASE_DIR, "data", "app.db")


def get_connection():
    """
    Create and return a safe SQLite connection.
    Ensures directory exists and handles errors.
    """
    try:
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    except Exception as e:
        print(f"❌ Failed to create DB directory: {e}")
        traceback.print_exc()
        raise

    try:
        conn = sqlite3.connect(DB_FILE, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # return rows as dict-like
        return conn
    except sqlite3.Error as e:
        print(f"❌ SQLite connection error: {e}")
        traceback.print_exc()
        raise
    except Exception as e:
        print(f"❌ Unexpected error creating DB connection: {e}")
        traceback.print_exc()
        raise


def execute_query(query, params=None, commit=False, fetch=False, raise_on_error=False):
    """
    Execute a single query safely with optional commit.
    Returns:
    - lastrowid when commit=True
    - fetched rows when fetch=True
    - True on success for non-commit, non-fetch
    - None on error
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        if commit:
            conn.commit()
            return cursor.lastrowid
        if fetch:
            return cursor.fetchall()
        return True
    except sqlite3.IntegrityError as e:
        print(f"❌ Integrity error: {e}")
        traceback.print_exc()
        if raise_on_error:
            raise
    except sqlite3.OperationalError as e:
        print(f"❌ Operational error: {e}")
        traceback.print_exc()
        if raise_on_error:
            raise
    except sqlite3.DatabaseError as e:
        print(f"❌ Database error: {e}")
        traceback.print_exc()
        if raise_on_error:
            raise
    except Exception as e:
        print(f"❌ Unexpected error executing query: {e}")
        traceback.print_exc()
        if raise_on_error:
            raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return None


def init_db():
    """
    Initialize all tables with detailed error handling.
    """
    table_queries = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            first_name TEXT,
            last_name TEXT,
            dob TEXT,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            is_active INTEGER DEFAULT 1,
            plan_code TEXT DEFAULT 'free',
            plan_started_at TEXT,
            plan_expires_at TEXT,
            auto_renew INTEGER DEFAULT 0,
            is_trial INTEGER DEFAULT 1,
            trial_ends_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            session_id TEXT,
            question TEXT,
            answer TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            session_title TEXT,
            session_content TEXT,
            selected_content TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS lesson_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            session_id TEXT,
            chapter TEXT,
            plan_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS lesson_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            session_id TEXT,
            step_id INTEGER,
            status TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS lesson_quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            session_id TEXT,
            step_id INTEGER,
            quiz_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            selected_content TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS lesson_quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            session_id TEXT,
            step_id INTEGER,
            question TEXT,
            user_answer TEXT,
            correct_answer TEXT,
            is_correct INTEGER,
            answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS usage_counters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            uploads_count INTEGER DEFAULT 0,
            quiz_count INTEGER DEFAULT 0,
            flashcard_count INTEGER DEFAULT 0,
            lesson_count INTEGER DEFAULT 0,
            ask_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, period_start, period_end)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS message_catalog (
            message_id TEXT PRIMARY KEY,
            level TEXT NOT NULL,
            template TEXT NOT NULL,
            user_friendly_text TEXT NOT NULL,
            developer_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS user_storage_roots (
            user_id TEXT PRIMARY KEY,
            email_hash_root TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS uploaded_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            class_name TEXT NOT NULL,
            subject_name TEXT NOT NULL,
            folder_name TEXT NOT NULL,
            file_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            file_sha256 TEXT,
            mime_type TEXT,
            size_bytes INTEGER,
            upload_status TEXT DEFAULT 'UPLOADED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS indexing_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            scope_type TEXT NOT NULL,
            scope_ref TEXT,
            status TEXT DEFAULT 'QUEUED',
            started_at TEXT,
            ended_at TEXT,
            error_code TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS file_index_status (
            file_id INTEGER PRIMARY KEY,
            indexed INTEGER DEFAULT 0,
            index_version TEXT,
            last_indexed_at TEXT,
            status_reason TEXT,
            message_id TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS lesson_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_plan_id INTEGER NOT NULL,
            card_order INTEGER NOT NULL,
            title TEXT NOT NULL,
            card_type TEXT,
            content_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS lesson_card_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            lesson_plan_id INTEGER NOT NULL,
            card_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            completed_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, lesson_plan_id, card_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS learning_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            session_id TEXT,
            lesson_plan_id INTEGER,
            card_id INTEGER,
            artifact_type TEXT NOT NULL,
            title TEXT,
            tags TEXT,
            payload_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            selected_content TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS profile_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            changes_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    ]

    for query in table_queries:
        result = execute_query(query, commit=True, raise_on_error=True)
        if result is None:
            print(f"⚠️ Failed to create table. Check logs for details.")

    # Backward-compatible migration for pre-existing DB files.
    migrate_user_schema()
    migrate_lesson_plan_schema()
    migrate_plan_schema()
    migrate_file_management_schema()
    migrate_lesson_card_schema()
    migrate_profile_schema()
    seed_message_catalog()

    # Initialize default users
    try:
        from .user_manager import init_default_users
        conn = get_connection()
        init_default_users(conn)
        conn.close()
    except Exception as e:
        print(f"⚠️ Error initializing default users: {e}")

    print(f"✅ Database initialized at: {DB_FILE}")


def migrate_user_schema():
    """
    Ensure users table has all profile/auth columns required by the new flow.
    Safe to run multiple times.
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in cursor.fetchall()}

        alter_statements = []
        if "email" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN email TEXT")
        if "first_name" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN first_name TEXT")
        if "last_name" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN last_name TEXT")
        if "dob" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN dob TEXT")
        if "plan_code" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN plan_code TEXT DEFAULT 'free'")
        if "plan_started_at" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN plan_started_at TEXT")
        if "plan_expires_at" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN plan_expires_at TEXT")
        if "auto_renew" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN auto_renew INTEGER DEFAULT 0")
        if "is_trial" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN is_trial INTEGER DEFAULT 1")
        if "trial_ends_at" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN trial_ends_at TEXT")

        for stmt in alter_statements:
            cursor.execute(stmt)

        # Keep email unique for registered users.
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email)")
        conn.commit()
    except Exception as e:
        print(f"⚠️ User schema migration warning: {e}")
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def migrate_plan_schema():
    """Ensure policy and usage tables required for plan enforcement exist."""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_counters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                uploads_count INTEGER DEFAULT 0,
                quiz_count INTEGER DEFAULT 0,
                flashcard_count INTEGER DEFAULT 0,
                lesson_count INTEGER DEFAULT 0,
                ask_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, period_start, period_end)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS message_catalog (
                message_id TEXT PRIMARY KEY,
                level TEXT NOT NULL,
                template TEXT NOT NULL,
                user_friendly_text TEXT NOT NULL,
                developer_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    except Exception as e:
        print(f"⚠️ Plan schema migration warning: {e}")
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def migrate_profile_schema():
    """Ensure profile audit table exists for immutable-email profile updates."""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS profile_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                changes_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    except Exception as e:
        print(f"⚠️ Profile schema migration warning: {e}")
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def seed_message_catalog():
    """Seed default user-facing messages for traceability."""
    rows = [
        ("MSG-1000", "INFO", "Operation completed", "Operation completed successfully.", "Default success"),
        ("MSG-1400", "WARN", "Invalid request", "The request could not be processed. Please check inputs and try again.", "Validation and bad request"),
        ("MSG-1102", "ALERT", "Background indexing in progress", "The file is still indexing. Please try again shortly.", "Shown when dependent content is not ready"),
        ("MSG-1201", "WARN", "Plan limit reached", "Your current plan limit has been reached for this action.", "Quota middleware"),
        ("MSG-1301", "INFO", "Upload accepted", "File uploaded successfully. Indexing has started in the background.", "Upload endpoint"),
        ("MSG-1302", "ALERT", "Not indexed yet", "This content is still being processed in the background.", "Indexed state gate"),
        ("MSG-1303", "ERROR", "Invalid name", "Use only letters, numbers, and hyphens for names.", "File/folder naming constraints"),
        ("MSG-1304", "ERROR", "Invalid file type", "Only PDF files are supported for upload right now.", "Upload file type validation"),
        ("MSG-1305", "INFO", "Reindex started", "Reindex has started for the selected scope.", "Reindex endpoint"),
        ("MSG-1401", "ERROR", "Unauthorized", "You are not authorized to perform this action.", "RBAC/auth"),
        ("MSG-1404", "ERROR", "Resource not found", "The requested resource could not be found.", "Missing entity"),
        ("MSG-1500", "CRITICAL", "Internal server error", "Something went wrong on the server. Please try again.", "Unhandled exceptions"),
    ]

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT OR IGNORE INTO message_catalog
            (message_id, level, template, user_friendly_text, developer_notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    except Exception as e:
        print(f"⚠️ Message catalog seed warning: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def migrate_file_management_schema():
    """Ensure upload/indexing tables required for file management exist."""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_storage_roots (
                user_id TEXT PRIMARY KEY,
                email_hash_root TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                class_name TEXT NOT NULL,
                subject_name TEXT NOT NULL,
                folder_name TEXT NOT NULL,
                file_name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                file_sha256 TEXT,
                mime_type TEXT,
                size_bytes INTEGER,
                upload_status TEXT DEFAULT 'UPLOADED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS indexing_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                scope_type TEXT NOT NULL,
                scope_ref TEXT,
                status TEXT DEFAULT 'QUEUED',
                started_at TEXT,
                ended_at TEXT,
                error_code TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS file_index_status (
                file_id INTEGER PRIMARY KEY,
                indexed INTEGER DEFAULT 0,
                index_version TEXT,
                last_indexed_at TEXT,
                status_reason TEXT,
                message_id TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    except Exception as e:
        print(f"⚠️ File management schema migration warning: {e}")
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def migrate_lesson_card_schema():
    """Ensure normalized lesson card and artifact tables exist."""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_plan_id INTEGER NOT NULL,
                card_order INTEGER NOT NULL,
                title TEXT NOT NULL,
                card_type TEXT,
                content_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_card_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                lesson_plan_id INTEGER NOT NULL,
                card_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                completed_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, lesson_plan_id, card_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT,
                lesson_plan_id INTEGER,
                card_id INTEGER,
                artifact_type TEXT NOT NULL,
                title TEXT,
                tags TEXT,
                payload_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    except Exception as e:
        print(f"⚠️ Lesson card schema migration warning: {e}")
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def migrate_lesson_plan_schema():
    """
    Ensure lesson_plans table matches the current schema used by lesson endpoints.

    Legacy schema example:
    - id, content_id, lesson_json, created_at, updated_at

    Current schema:
    - id, user_id, session_id, chapter, plan_json, created_at
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(lesson_plans)")
        columns = [row[1] for row in cursor.fetchall()]
        if not columns:
            return

        required = {"user_id", "session_id", "chapter", "plan_json"}
        if required.issubset(set(columns)):
            return

        # Create replacement table with the expected schema.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_plans_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                session_id TEXT,
                chapter TEXT,
                plan_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if {"content_id", "lesson_json"}.issubset(set(columns)):
            cursor.execute(
                """
                SELECT id, content_id, lesson_json, created_at
                FROM lesson_plans
                ORDER BY id ASC
                """
            )
            legacy_rows = cursor.fetchall()

            for row in legacy_rows:
                legacy_id = row[0]
                content_id = row[1] or ""
                lesson_json_text = row[2] or "{}"
                created_at = row[3]

                try:
                    parsed = json.loads(lesson_json_text)
                    if not isinstance(parsed, dict):
                        parsed = {}
                except Exception:
                    parsed = {}

                session_id = parsed.get("session_id") or f"legacy-{legacy_id}"
                chapter = parsed.get("chapter") or content_id or "Legacy Lesson"
                steps = parsed.get("steps") if isinstance(parsed.get("steps"), list) else []

                normalized_plan = {
                    "session_id": session_id,
                    "chapter": chapter,
                    "steps": steps,
                }

                # Best-effort user mapping from chat history for the same session.
                cursor.execute(
                    "SELECT user_id FROM chat_history WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                    (session_id,),
                )
                owner = cursor.fetchone()
                user_id = owner[0] if owner and owner[0] else "student"

                cursor.execute(
                    """
                    INSERT INTO lesson_plans_new (id, user_id, session_id, chapter, plan_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        legacy_id,
                        user_id,
                        session_id,
                        chapter,
                        json.dumps(normalized_plan),
                        created_at or datetime.utcnow().isoformat(),
                    ),
                )

        cursor.execute("DROP TABLE lesson_plans")
        cursor.execute("ALTER TABLE lesson_plans_new RENAME TO lesson_plans")
        conn.commit()
    except Exception as e:
        print(f"⚠️ Lesson schema migration warning: {e}")
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def safe_insert(table, data: dict):
    """
    Safely insert data into a table.
    Returns last row id or None on failure.
    """
    try:
        keys = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        values = tuple(data.values())
        query = f"INSERT INTO {table} ({keys}) VALUES ({placeholders})"
        row_id = execute_query(query, values, commit=True, raise_on_error=True)
        if row_id is not None:
            return row_id
    except Exception as e:
        print(f"❌ Failed to insert into {table}: {e}")
        traceback.print_exc()
    return None


def safe_fetch(query, params=None):
    """
    Safely fetch data from the DB.
    Returns list of dicts or empty list on error.
    """
    try:
        rows = execute_query(query, params, fetch=True, raise_on_error=True)
        if rows:
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"❌ Failed to fetch data: {e}")
        traceback.print_exc()
    return []