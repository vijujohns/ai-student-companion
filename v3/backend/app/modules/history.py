"""
Chat history module
"""

from app.modules.db import get_connection
from datetime import datetime


def save_chat(user_id, session_id, question, answer):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO chat_history (user_id, session_id, question, answer, timestamp)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, session_id, question, answer, datetime.now().isoformat()))

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