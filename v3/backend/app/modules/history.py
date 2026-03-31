"""
Chat history module
"""

from .db import get_connection
from datetime import datetime


def save_chat(user_id, session_id, question, answer):
    conn = get_connection()
    cursor = conn.cursor()

    # Check if this exact (user, session, question) already has a row
    cursor.execute("""
    SELECT id, session_title FROM chat_history
    WHERE user_id=? AND session_id=? AND question=?
    ORDER BY id DESC
    LIMIT 1
    """, (user_id, session_id, question))

    existing = cursor.fetchone()

    if existing:
        # Update the answer in place — no duplicate rows
        cursor.execute("""
        UPDATE chat_history SET answer=?, timestamp=?
        WHERE id=?
        """, (answer, datetime.now().isoformat(), existing[0]))
    else:
        # First time saving this question — check for a session title to reuse
        cursor.execute("""
        SELECT session_title FROM chat_history
        WHERE user_id=? AND session_id=?
        LIMIT 1
        """, (user_id, session_id))
        title_row = cursor.fetchone()
        session_title = (title_row[0] if title_row and title_row[0] else question[:40])

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