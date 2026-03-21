"""
SQLite DB module for chat history & progress tracking
"""

import sqlite3
import os

# 🔥 Resolve project root dynamically
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))

DB_FILE = os.path.join(BASE_DIR, "data", "app.db")


def get_connection():
    """
    Create DB connection safely
    """

    # Ensure directory exists
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

    return sqlite3.connect(DB_FILE)


def init_db():
    """
    Initialize database tables
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        session_id TEXT,
        question TEXT,
        answer TEXT,
        timestamp TEXT
    )
    """)

    conn.commit()
    conn.close()

    print(f"✅ Database initialized at: {DB_FILE}")