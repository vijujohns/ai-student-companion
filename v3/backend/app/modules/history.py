"""
Chat history module
"""

from .db import get_connection
from datetime import datetime


_UNSET = object()


def save_chat(user_id, session_id, question, answer, session_content=_UNSET, selected_content=_UNSET):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        session_content_value = session_content if session_content is not _UNSET else None
        selected_content_value = selected_content if selected_content is not _UNSET else None

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
            if session_content is _UNSET and selected_content is _UNSET:
                cursor.execute("""
            UPDATE chat_history SET answer=?, timestamp=?
            WHERE id=?
            """, (answer, datetime.now().isoformat(), existing[0]))
            else:
                cursor.execute("""
            UPDATE chat_history
            SET answer=?, timestamp=?, session_content=?, selected_content=?
            WHERE id=?
            """, (answer, datetime.now().isoformat(), session_content_value, selected_content_value, existing[0]))
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
        (user_id, session_id, question, answer, timestamp, session_title, session_content, selected_content)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
                user_id,
                session_id,
                question,
                answer,
                datetime.now().isoformat(),
                session_title,
                session_content_value,
                selected_content_value,
            ))

        conn.commit()
    finally:
        conn.close()


def get_history(user_id, session_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
    SELECT question, answer, timestamp
    FROM chat_history
    WHERE user_id=? AND session_id=?
    ORDER BY id ASC
    """, (user_id, session_id))
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [
        {
            "question": r[0],
            "answer": r[1],
            "timestamp": r[2]
        }
        for r in rows
    ]