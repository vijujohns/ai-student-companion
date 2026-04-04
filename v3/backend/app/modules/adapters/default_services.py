from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from ..analytics import get_dashboard, get_mastery_stats, get_progress_insights, log_activity, update_mastery
from ..auth import authenticate_user, clear_auth_cookie, create_access_token, set_auth_cookie
from ..db import get_connection
from ..interfaces.service_ports import CommercialPort, IdentityAccessPort, LearningSessionPort, ProgressPort, RelationshipCollaborationPort, KnowledgePort
from ..policy import PLAN_LIMITS, get_usage_snapshot, get_user_plan
from ..subscriptions import activate_subscription, get_subscription_catalog, quote_subscription
from ..user_manager import register_user, reset_password_with_email_dob, update_user_profile
from ..lesson_plan import list_lesson_sessions, rename_lesson_session, delete_lesson_session
from ..quiz import list_quiz_sessions, get_latest_quiz_for_session, rename_quiz_session, delete_quiz_session
from ..artifacts import list_flashcard_sessions, get_latest_flashcard_artifact_for_session, rename_flashcard_session, delete_flashcard_session


class DefaultIdentityAccessService(IdentityAccessPort):
    def login(self, identifier: str, password: str, response: object) -> Dict:
        user = authenticate_user(identifier, password)
        if not user:
            raise PermissionError("Invalid credentials")
        token = create_access_token(user)
        set_auth_cookie(response, token)
        return {
            "access_token": token,
            "token_type": "bearer",
            "role": user["role"],
            "username": user["username"],
            "email": user.get("email"),
        }

    def get_auth_session(self, user: Dict) -> Dict:
        return {
            "authenticated": True,
            "username": user["username"],
            "email": user.get("email") or user["username"],
            "role": user.get("role", "user"),
        }

    def logout(self, response: object) -> Dict:
        clear_auth_cookie(response)
        return {"status": "logged_out"}

    def register(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        dob: str,
        password: str,
        role: str = "student",
    ) -> Dict:
        conn = get_connection()
        try:
            user = register_user(
                db_connection=conn,
                first_name=first_name,
                last_name=last_name,
                email=email,
                dob=dob,
                password=password,
                role=role,
            )
            return {
                "status": "registered",
                "email": user["email"],
                "role": user["role"],
            }
        finally:
            conn.close()

    def update_profile(
        self,
        *,
        username: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        dob: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Dict:
        conn = get_connection()
        try:
            return update_user_profile(
                db_connection=conn,
                username=username,
                first_name=first_name,
                last_name=last_name,
                dob=dob,
                email=email,
            )
        finally:
            conn.close()

    def reset_password(self, *, email: str, dob: str, new_password: str) -> bool:
        conn = get_connection()
        try:
            return reset_password_with_email_dob(conn, email, dob, new_password)
        finally:
            conn.close()


class DefaultRelationshipCollaborationService(RelationshipCollaborationPort):
    def get_user_by_email(self, email: str) -> Optional[Dict[str, str]]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT username, email, role FROM users WHERE email = ? LIMIT 1",
                (email,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {"username": row[0], "email": row[1], "role": row[2]}
        finally:
            conn.close()

    def resolve_student_user_id(self, student_identifier: str) -> Optional[str]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT username
                FROM users
                WHERE role = 'student' AND (username = ? OR email = ?)
                LIMIT 1
                """,
                (student_identifier, student_identifier),
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def has_relationship_access(self, student_user_id: str, requester: Dict) -> bool:
        student_user_id = self.resolve_student_user_id(student_user_id) or student_user_id
        if requester.get("role") == "admin":
            return True
        if requester.get("username") == student_user_id:
            return True
        if requester.get("role") not in {"teacher", "parent"}:
            return False

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1
                FROM student_relationships
                WHERE student_user_id = ?
                  AND related_user_id = ?
                  AND relation_role = ?
                LIMIT 1
                """,
                (student_user_id, requester.get("username"), requester.get("role")),
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def link_student(
        self,
        student_user_id: str,
        related_user_id: str,
        relation_role: str,
        relation_label: Optional[str],
    ) -> None:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO student_relationships
                (student_user_id, related_user_id, relation_role, relation_label)
                VALUES (?, ?, ?, ?)
                """,
                (student_user_id, related_user_id, relation_role, relation_label),
            )
            conn.commit()
        finally:
            conn.close()

    def list_students_for_related(self, related_user_id: str, relation_role: str) -> List[Dict]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT r.student_user_id, u.email, u.first_name, u.last_name, r.relation_label, r.created_at
                FROM student_relationships r
                JOIN users u ON u.username = r.student_user_id
                WHERE r.related_user_id = ? AND r.relation_role = ?
                ORDER BY r.created_at DESC
                """,
                (related_user_id, relation_role),
            )
            rows = cursor.fetchall()
            return [
                {
                    "username": row[0],
                    "email": row[1],
                    "first_name": row[2] or "",
                    "last_name": row[3] or "",
                    "relation_label": row[4],
                    "linked_at": row[5],
                }
                for row in rows
            ]
        finally:
            conn.close()

    def list_mentors_for_student(self, student_user_id: str) -> List[Dict]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT r.related_user_id, u.email, u.first_name, u.last_name, r.relation_role, r.relation_label, r.created_at
                FROM student_relationships r
                JOIN users u ON u.username = r.related_user_id
                WHERE r.student_user_id = ?
                ORDER BY r.created_at DESC
                """,
                (student_user_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "username": row[0],
                    "email": row[1],
                    "first_name": row[2] or "",
                    "last_name": row[3] or "",
                    "role": row[4],
                    "relation_label": row[5],
                    "linked_at": row[6],
                }
                for row in rows
            ]
        finally:
            conn.close()

    def create_note(
        self,
        student_user_id: str,
        author_user_id: str,
        author_role: str,
        note_text: str,
        visibility: str,
    ) -> int:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO collaboration_notes
                (student_user_id, author_user_id, author_role, note_text, visibility)
                VALUES (?, ?, ?, ?, ?)
                """,
                (student_user_id, author_user_id, author_role, note_text, visibility),
            )
            note_id = cursor.lastrowid
            conn.commit()
            return note_id
        finally:
            conn.close()

    def list_notes(self, student_user_id: str, requester_role: str, requester_user_id: str) -> List[Dict]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if requester_role in {"student", "admin"}:
                cursor.execute(
                    """
                    SELECT id, author_user_id, author_role, note_text, visibility, created_at
                    FROM collaboration_notes
                    WHERE student_user_id = ?
                    ORDER BY created_at DESC, id DESC
                    """,
                    (student_user_id,),
                )
            elif requester_role == "parent":
                cursor.execute(
                    """
                    SELECT id, author_user_id, author_role, note_text, visibility, created_at
                    FROM collaboration_notes
                    WHERE student_user_id = ?
                      AND (visibility IN ('all', 'guardians') OR author_user_id = ?)
                    ORDER BY created_at DESC, id DESC
                    """,
                    (student_user_id, requester_user_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, author_user_id, author_role, note_text, visibility, created_at
                    FROM collaboration_notes
                    WHERE student_user_id = ?
                      AND (visibility = 'all' OR author_user_id = ?)
                    ORDER BY created_at DESC, id DESC
                    """,
                    (student_user_id, requester_user_id),
                )
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "author_user_id": row[1],
                    "author_role": row[2],
                    "note_text": row[3],
                    "visibility": row[4],
                    "created_at": row[5],
                }
                for row in rows
            ]
        finally:
            conn.close()

    def update_note(
        self,
        student_user_id: str,
        note_id: int,
        updates: Dict,
        requester_user_id: str,
        requester_role: str,
    ) -> Optional[Dict]:
        allowed_fields = {"note_text", "visibility"}
        filtered_updates = {
            key: value
            for key, value in (updates or {}).items()
            if key in allowed_fields and value is not None
        }
        if not filtered_updates:
            return None

        conn = get_connection()
        try:
            cursor = conn.cursor()
            if requester_role == "admin":
                cursor.execute(
                    "SELECT id, author_user_id, author_role, note_text, visibility, created_at FROM collaboration_notes WHERE student_user_id = ? AND id = ? LIMIT 1",
                    (student_user_id, note_id),
                )
            else:
                cursor.execute(
                    "SELECT id, author_user_id, author_role, note_text, visibility, created_at FROM collaboration_notes WHERE student_user_id = ? AND id = ? AND author_user_id = ? LIMIT 1",
                    (student_user_id, note_id, requester_user_id),
                )
            row = cursor.fetchone()
            if not row:
                return None

            set_clause = ", ".join(f"{field} = ?" for field in filtered_updates)
            values = list(filtered_updates.values())
            if requester_role == "admin":
                cursor.execute(
                    f"UPDATE collaboration_notes SET {set_clause} WHERE student_user_id = ? AND id = ?",
                    values + [student_user_id, note_id],
                )
            else:
                cursor.execute(
                    f"UPDATE collaboration_notes SET {set_clause} WHERE student_user_id = ? AND id = ? AND author_user_id = ?",
                    values + [student_user_id, note_id, requester_user_id],
                )
            conn.commit()

            cursor.execute(
                "SELECT id, author_user_id, author_role, note_text, visibility, created_at FROM collaboration_notes WHERE student_user_id = ? AND id = ? LIMIT 1",
                (student_user_id, note_id),
            )
            updated_row = cursor.fetchone()
            if not updated_row:
                return None
            return {
                "id": updated_row[0],
                "author_user_id": updated_row[1],
                "author_role": updated_row[2],
                "note_text": updated_row[3],
                "visibility": updated_row[4],
                "created_at": updated_row[5],
            }
        finally:
            conn.close()

    def delete_note(self, student_user_id: str, note_id: int, requester_user_id: str, requester_role: str) -> bool:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if requester_role == "admin":
                cursor.execute(
                    "DELETE FROM collaboration_notes WHERE student_user_id = ? AND id = ?",
                    (student_user_id, note_id),
                )
            else:
                cursor.execute(
                    "DELETE FROM collaboration_notes WHERE student_user_id = ? AND id = ? AND author_user_id = ?",
                    (student_user_id, note_id, requester_user_id),
                )
            deleted = cursor.rowcount > 0
            if deleted:
                conn.commit()
            return deleted
        finally:
            conn.close()

    def create_assignment(
        self,
        student_user_id: str,
        author_user_id: str,
        author_role: str,
        title: str,
        description: str,
        action_tab: str,
        cta_label: str,
        chapter_hint: Optional[str],
        context_hint: Optional[str],
        due_label: Optional[str] = None,
    ) -> int:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO mentor_assignments
                (student_user_id, author_user_id, author_role, title, description, action_tab, cta_label, chapter_hint, context_hint, due_label, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'assigned')
                """,
                (
                    student_user_id,
                    author_user_id,
                    author_role,
                    title,
                    description,
                    action_tab,
                    cta_label,
                    chapter_hint or "",
                    context_hint or "",
                    due_label,
                ),
            )
            assignment_id = cursor.lastrowid
            conn.commit()
            return assignment_id
        finally:
            conn.close()

    @staticmethod
    def _assignment_row_to_dict(row) -> Dict:
        return {
            "id": row[0],
            "author_user_id": row[1],
            "author_role": row[2],
            "title": row[3],
            "description": row[4],
            "action_tab": row[5],
            "cta_label": row[6],
            "chapter_hint": row[7],
            "context_hint": row[8],
            "due_label": row[9],
            "status": row[10],
            "created_at": row[11],
            "completed_at": row[12],
        }

    def _get_assignment(self, cursor, student_user_id: str, assignment_id: int) -> Optional[Dict]:
        cursor.execute(
            """
            SELECT id, author_user_id, author_role, title, description, action_tab, cta_label, chapter_hint, context_hint, due_label, status, created_at, completed_at
            FROM mentor_assignments
            WHERE student_user_id = ? AND id = ?
            LIMIT 1
            """,
            (student_user_id, assignment_id),
        )
        row = cursor.fetchone()
        return self._assignment_row_to_dict(row) if row else None

    def list_assignments(self, student_user_id: str) -> List[Dict]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, author_user_id, author_role, title, description, action_tab, cta_label, chapter_hint, context_hint, due_label, status, created_at, completed_at
                FROM mentor_assignments
                WHERE student_user_id = ?
                ORDER BY CASE WHEN status = 'assigned' THEN 0 ELSE 1 END, created_at DESC, id DESC
                """,
                (student_user_id,),
            )
            rows = cursor.fetchall()
            return [self._assignment_row_to_dict(row) for row in rows]
        finally:
            conn.close()

    def update_assignment(self, student_user_id: str, assignment_id: int, updates: Dict) -> Optional[Dict]:
        allowed_fields = {
            "title",
            "description",
            "action_tab",
            "cta_label",
            "chapter_hint",
            "context_hint",
            "due_label",
            "status",
            "completed_at",
        }
        filtered_updates = {key: value for key, value in (updates or {}).items() if key in allowed_fields}
        conn = get_connection()
        try:
            cursor = conn.cursor()
            current = self._get_assignment(cursor, student_user_id, assignment_id)
            if not current:
                return None

            if "status" in filtered_updates:
                filtered_updates["completed_at"] = (
                    datetime.now(timezone.utc).isoformat() if filtered_updates.get("status") == "completed" else None
                )

            if filtered_updates:
                set_clause = ", ".join(f"{field} = ?" for field in filtered_updates)
                values = list(filtered_updates.values()) + [assignment_id, student_user_id]
                cursor.execute(
                    f"UPDATE mentor_assignments SET {set_clause} WHERE id = ? AND student_user_id = ?",
                    values,
                )
                conn.commit()

            return self._get_assignment(cursor, student_user_id, assignment_id)
        finally:
            conn.close()

    def delete_assignment(self, student_user_id: str, assignment_id: int) -> bool:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM mentor_assignments WHERE student_user_id = ? AND id = ?",
                (student_user_id, assignment_id),
            )
            deleted = cursor.rowcount > 0
            if deleted:
                conn.commit()
            return deleted
        finally:
            conn.close()


class DefaultProgressService(ProgressPort):
    def get_dashboard(self, user_id: str) -> Dict:
        return get_dashboard(user_id)

    def get_insights(self, user_id: str) -> Dict:
        return get_progress_insights(user_id)

    def get_study_plan(self, user_id: str) -> Dict:
        from ..analytics import get_study_plan
        return get_study_plan(user_id)

    def get_mastery_stats(self, user_id: str) -> List[Dict]:
        return get_mastery_stats(user_id)

    def log_activity(
        self,
        user_id: str,
        activity_type: str,
        subject: str = "",
        chapter: str = "",
        duration_seconds: int = 0,
    ) -> int:
        return log_activity(
            user_id=user_id,
            activity_type=activity_type,
            subject=subject,
            chapter=chapter,
            duration_seconds=duration_seconds,
        )

    def update_mastery(
        self,
        user_id: str,
        subject: str,
        chapter: str,
        correct: int,
        total: int,
    ) -> float:
        return update_mastery(user_id, subject, chapter, correct, total)

    def get_student_progress(self, student_user_id: str) -> Tuple[Dict, List[Dict]]:
        return self.get_dashboard(student_user_id), self.get_mastery_stats(student_user_id)

    def update_study_plan_item(self, user_id: str, item_id: str, item_type: str, completed: bool) -> Dict:
        from ..analytics import save_study_plan_item_state
        return save_study_plan_item_state(user_id, item_id, item_type, completed)


class DefaultKnowledgeService(KnowledgePort):
    """In-process adapter for the Knowledge + Ingestion domain."""

    def __init__(self, kb_dir: str) -> None:
        self._kb_dir = kb_dir

    def _safe_path(self, *parts: str) -> str:
        import os
        kb = os.path.realpath(self._kb_dir)
        for part in parts:
            if not part or any(c in part for c in ("/", "\\", "..")):
                raise ValueError(f"Invalid path component: {part!r}")
        candidate = os.path.realpath(os.path.join(kb, *parts))
        if not candidate.startswith(kb + os.sep) and candidate != kb:
            raise ValueError("Path traversal detected")
        return candidate

    def list_classes(self) -> List[str]:
        import os
        if not os.path.exists(self._kb_dir):
            return []
        return sorted(
            [d for d in os.listdir(self._kb_dir) if os.path.isdir(os.path.join(self._kb_dir, d))]
        )

    def list_subjects(self, class_name: str) -> List[str]:
        import os
        p = self._safe_path(class_name)
        if not os.path.exists(p):
            return []
        return sorted([d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d))])

    def list_folders(self, class_name: str, subject: str) -> List[str]:
        import os
        p = self._safe_path(class_name, subject)
        if not os.path.exists(p):
            return []
        return sorted([d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d))])

    def list_contents(self, class_name: str, subject: str, folder: str) -> List[Dict]:
        import os
        from ..file_management import make_kb_content_ref
        folder_path = self._safe_path(class_name, subject, folder)
        if not os.path.exists(folder_path):
            return []
        result = []
        for f in os.listdir(folder_path):
            full_path = os.path.join(folder_path, f)
            if os.path.isfile(full_path) and f.lower().endswith(".pdf"):
                relative_path = os.path.relpath(full_path, self._kb_dir)
                result.append(
                    {"title": os.path.splitext(f)[0], "content_id": make_kb_content_ref(relative_path)}
                )
        return result

    def file_tree(self, user: Dict) -> List[Dict]:
        from ..file_management import get_files_tree
        return get_files_tree(user)

    def index_status(self, user: Dict, file_id: Optional[int] = None) -> List[Dict]:
        from ..file_management import get_index_status
        return get_index_status(user, file_id=file_id)

    def queue_reindex(self, user: Dict, scope: str = "changed", file_id: Optional[int] = None) -> Dict:
        from ..file_management import queue_reindex as _queue_reindex
        return _queue_reindex(user, scope=scope, file_id=file_id)


class DefaultCommercialService(CommercialPort):
    def get_plan_me(self, user_id: str) -> Dict:
        return {
            "plan": get_user_plan(user_id),
            "usage": get_usage_snapshot(user_id),
        }

    def get_plan_limits(self, user_id: str) -> Dict:
        current = get_user_plan(user_id)
        return {
            "plan_code": current["plan_code"],
            "effective_limits": current["limits"],
            "all_limits": PLAN_LIMITS,
        }

    def get_subscription_catalog(self) -> Dict:
        return get_subscription_catalog()

    def quote_subscription(
        self,
        class_names: List[str],
        promo_code: Optional[str] = None,
        auto_renew: bool = False,
    ) -> Dict:
        quote = quote_subscription(class_names, promo_code=promo_code)
        quote["auto_renew"] = bool(auto_renew)
        return quote

    def activate_subscription(
        self,
        user_id: str,
        class_names: List[str],
        promo_code: Optional[str] = None,
        auto_renew: bool = False,
        payment_reference: Optional[str] = None,
    ) -> Dict:
        result = activate_subscription(
            user_id=user_id,
            class_names=class_names,
            promo_code=promo_code,
            auto_renew=auto_renew,
        )
        result["payment_reference"] = payment_reference
        return result


class DefaultLearningSessionService(LearningSessionPort):
    def list_chat_sessions(self, user_id: str) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    ch.session_id,
                    ch.session_title,
                    ch.timestamp,
                    ch.selected_content
                FROM chat_history ch
                INNER JOIN (
                    SELECT session_id, MAX(id) AS latest_id
                    FROM chat_history
                    WHERE user_id=?
                    GROUP BY session_id
                ) latest
                    ON latest.session_id = ch.session_id
                   AND latest.latest_id = ch.id
                WHERE ch.user_id=?
                ORDER BY ch.id DESC
                """,
                (user_id, user_id),
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        return [
            {
                "id": r[0],
                "title": r[1] if r[1] else "New Chat",
                "last_updated": r[2],
                "selected_content": r[3],
            }
            for r in rows
        ]

    def rename_chat_session(self, user_id: str, session_id: str, title: str) -> Dict:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE chat_history
                SET session_title=?
                WHERE user_id=? AND session_id=?
                """,
                (title, user_id, session_id),
            )
            conn.commit()
        finally:
            conn.close()
        return {"status": "updated"}

    def delete_chat_session(self, user_id: str, session_id: str) -> Dict:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                DELETE FROM chat_history
                WHERE user_id=? AND session_id=?
                """,
                (user_id, session_id),
            )
            conn.commit()
        finally:
            conn.close()
        return {"status": "deleted"}

    def get_session_content(self, user: Dict, session_id: str) -> Dict:
        from ..file_management import resolve_content_reference
        from fastapi import HTTPException

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT session_content FROM chat_history
                WHERE user_id=? AND session_id=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (user["username"], session_id),
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        session_content = row[0] if row else None
        if session_content:
            try:
                resolved = resolve_content_reference(user, session_content)
                session_content = resolved["content_id"] if resolved else None
            except HTTPException:
                session_content = None
        return {"session_content": session_content}

    def set_session_content(self, user: Dict, session_id: str, content_id: Optional[str]) -> Dict:
        from ..file_management import resolve_content_reference

        resolved = resolve_content_reference(user, content_id) if content_id else None
        canonical_content_id = resolved["content_id"] if resolved else None
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE chat_history
                SET session_content=?, selected_content=?
                WHERE user_id=? AND session_id=?
                """,
                (canonical_content_id, canonical_content_id, user["username"], session_id),
            )
            conn.commit()
        finally:
            conn.close()
        return {"status": "updated", "session_content": canonical_content_id}

    def list_lesson_sessions(self, user_id: str) -> List[Dict]:
        return list_lesson_sessions(user_id)

    def rename_lesson_session(self, user_id: str, session_id: str, title: str) -> Dict:
        return rename_lesson_session(user_id, session_id, title)

    def delete_lesson_session(self, user_id: str, session_id: str) -> Dict:
        return delete_lesson_session(user_id, session_id)

    def list_quiz_sessions(self, user_id: str) -> List[Dict]:
        return list_quiz_sessions(user_id)

    def rename_quiz_session(self, user_id: str, session_id: str, title: str) -> Dict:
        return rename_quiz_session(user_id, session_id, title)

    def delete_quiz_session(self, user_id: str, session_id: str) -> Dict:
        return delete_quiz_session(user_id, session_id)

    def get_latest_quiz(self, user_id: str, session_id: str) -> Optional[Dict]:
        return get_latest_quiz_for_session(user_id, session_id)

    def list_flashcard_sessions(self, user_id: str) -> List[Dict]:
        return list_flashcard_sessions(user_id)

    def rename_flashcard_session(self, user_id: str, session_id: str, title: str) -> Dict:
        return rename_flashcard_session(user_id, session_id, title)

    def delete_flashcard_session(self, user_id: str, session_id: str) -> Dict:
        return delete_flashcard_session(user_id, session_id)

    def get_latest_flashcards(self, user_id: str, session_id: str) -> Optional[Dict]:
        return get_latest_flashcard_artifact_for_session(user_id, session_id)


@dataclass(frozen=True)
class ServiceRegistry:
    identity: IdentityAccessPort
    relationships: RelationshipCollaborationPort
    progress: ProgressPort
    knowledge: KnowledgePort
    commercial: CommercialPort
    learning: LearningSessionPort


def get_default_service_registry() -> ServiceRegistry:
    import os as _os
    kb_dir = _os.path.join(
        _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "../../../../")),
        "knowledge_base",
    )
    return ServiceRegistry(
        identity=DefaultIdentityAccessService(),
        relationships=DefaultRelationshipCollaborationService(),
        progress=DefaultProgressService(),
        knowledge=DefaultKnowledgeService(kb_dir=kb_dir),
        commercial=DefaultCommercialService(),
        learning=DefaultLearningSessionService(),
    )
