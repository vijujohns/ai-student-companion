"""
Progress tracking utilities for lesson sessions.
"""

from typing import Dict, List, Optional

from .db import get_connection


def record_progress(user_id: str, session_id: str, step_id: int, status: str) -> Dict[str, str]:
	conn = get_connection()
	cursor = conn.cursor()
	cursor.execute(
		"""
		INSERT INTO lesson_progress (user_id, session_id, step_id, status)
		VALUES (?, ?, ?, ?)
		""",
		(user_id, session_id, step_id, status),
	)
	conn.commit()
	conn.close()
	return {"status": "updated"}


def get_latest_step_status(user_id: str, session_id: str, step_id: int) -> Optional[str]:
	conn = get_connection()
	cursor = conn.cursor()
	cursor.execute(
		"""
		SELECT status FROM lesson_progress
		WHERE user_id=? AND session_id=? AND step_id=?
		ORDER BY id DESC LIMIT 1
		""",
		(user_id, session_id, step_id),
	)
	row = cursor.fetchone()
	conn.close()
	return row[0] if row else None


def get_completed_step_ids(user_id: str, session_id: str) -> List[int]:
	conn = get_connection()
	cursor = conn.cursor()
	cursor.execute(
		"""
		SELECT step_id, status FROM lesson_progress
		WHERE user_id=? AND session_id=?
		ORDER BY id ASC
		""",
		(user_id, session_id),
	)
	rows = cursor.fetchall()
	conn.close()

	latest_by_step = {}
	for step_id, status in rows:
		latest_by_step[int(step_id)] = status

	return [step_id for step_id, status in latest_by_step.items() if status == "completed"]


def reset_progress(user_id: str, session_id: str) -> Dict[str, str]:
	conn = get_connection()
	cursor = conn.cursor()
	cursor.execute(
		"""
		DELETE FROM lesson_progress
		WHERE user_id=? AND session_id=?
		""",
		(user_id, session_id),
	)
	conn.commit()
	conn.close()
	return {"status": "progress reset"}
