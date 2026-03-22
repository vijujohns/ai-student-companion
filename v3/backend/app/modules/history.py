"""
Chat history module
"""

from app.modules.db import get_connection
from datetime import datetime


def save_chat(user_id, session_id, question, answer):
    conn = get_connection()
    cursor = conn.cursor()

    # 🔥 Check if session already has a title
    cursor.execute("""
    SELECT session_title FROM chat_history
    WHERE user_id=? AND session_id=?
    LIMIT 1
    """, (user_id, session_id))

    row = cursor.fetchone()

    if row and row[0]:
        # Existing session → reuse title
        session_title = row[0]
    else:
        # First message → create title from question
        session_title = question[:40]

    # ✅ Insert with session_title (backward compatible)
    cursor.execute("""
    INSERT INTO chat_history 
    (user_id, session_id, question, answer, timestamp, session_title)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        session_id,
        question,
        answer,
        datetime.now().isoformat(),
        session_title
    ))

    conn.commit()
    conn.close()


def get_history(user_id, session_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT question, answer, timestamp
    FROM chat_history
    WHERE user_id=? AND session_id=?
    ORDER BY id ASC
    """, (user_id, session_id))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "question": r[0],
            "answer": r[1],
            "timestamp": r[2]
        }
        for r in rows
    ]