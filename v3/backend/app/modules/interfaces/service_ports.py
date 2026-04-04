from __future__ import annotations

from typing import Dict, List, Optional, Protocol, Tuple


class IdentityAccessPort(Protocol):
    def login(self, identifier: str, password: str, response: object) -> Dict:
        ...

    def get_auth_session(self, user: Dict) -> Dict:
        ...

    def logout(self, response: object) -> Dict:
        ...

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
        ...

    def update_profile(
        self,
        *,
        username: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        dob: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Dict:
        ...

    def reset_password(self, *, email: str, dob: str, new_password: str) -> bool:
        ...


class RelationshipCollaborationPort(Protocol):
    def get_user_by_email(self, email: str) -> Optional[Dict[str, str]]:
        ...

    def resolve_student_user_id(self, student_identifier: str) -> Optional[str]:
        ...

    def has_relationship_access(self, student_user_id: str, requester: Dict) -> bool:
        ...

    def link_student(
        self,
        student_user_id: str,
        related_user_id: str,
        relation_role: str,
        relation_label: Optional[str],
    ) -> None:
        ...

    def list_students_for_related(self, related_user_id: str, relation_role: str) -> List[Dict]:
        ...

    def list_mentors_for_student(self, student_user_id: str) -> List[Dict]:
        ...

    def create_note(
        self,
        student_user_id: str,
        author_user_id: str,
        author_role: str,
        note_text: str,
        visibility: str,
    ) -> int:
        ...

    def list_notes(self, student_user_id: str, requester_role: str, requester_user_id: str) -> List[Dict]:
        ...

    def update_note(
        self,
        student_user_id: str,
        note_id: int,
        updates: Dict,
        requester_user_id: str,
        requester_role: str,
    ) -> Optional[Dict]:
        ...

    def delete_note(self, student_user_id: str, note_id: int, requester_user_id: str, requester_role: str) -> bool:
        ...

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
        ...

    def list_assignments(self, student_user_id: str) -> List[Dict]:
        ...

    def update_assignment(self, student_user_id: str, assignment_id: int, updates: Dict) -> Optional[Dict]:
        ...

    def delete_assignment(self, student_user_id: str, assignment_id: int) -> bool:
        ...


class ProgressPort(Protocol):
    def get_dashboard(self, user_id: str) -> Dict:
        ...

    def get_insights(self, user_id: str) -> Dict:
        ...

    def get_study_plan(self, user_id: str) -> Dict:
        ...

    def get_mastery_stats(self, user_id: str) -> List[Dict]:
        ...

    def log_activity(
        self,
        user_id: str,
        activity_type: str,
        subject: str = "",
        chapter: str = "",
        duration_seconds: int = 0,
    ) -> int:
        ...

    def update_mastery(
        self,
        user_id: str,
        subject: str,
        chapter: str,
        correct: int,
        total: int,
    ) -> float:
        ...

    def get_student_progress(self, student_user_id: str) -> Tuple[Dict, List[Dict]]:
        ...

    def update_study_plan_item(
        self,
        user_id: str,
        item_id: str,
        item_type: str,
        completed: bool,
    ) -> Dict:
        ...


class KnowledgePort(Protocol):
    def list_classes(self) -> List[str]:
        ...

    def list_subjects(self, class_name: str) -> List[str]:
        ...

    def list_folders(self, class_name: str, subject: str) -> List[str]:
        ...

    def list_contents(self, class_name: str, subject: str, folder: str) -> List[Dict]:
        ...

    def file_tree(self, user: Dict) -> List[Dict]:
        ...

    def index_status(self, user: Dict, file_id: Optional[int] = None) -> List[Dict]:
        ...

    def queue_reindex(self, user: Dict, scope: str = "changed", file_id: Optional[int] = None) -> Dict:
        ...


class CommercialPort(Protocol):
    def get_plan_me(self, user_id: str) -> Dict:
        ...

    def get_plan_limits(self, user_id: str) -> Dict:
        ...

    def get_subscription_catalog(self) -> Dict:
        ...

    def quote_subscription(
        self,
        class_names: List[str],
        promo_code: Optional[str] = None,
        auto_renew: bool = False,
    ) -> Dict:
        ...

    def activate_subscription(
        self,
        user_id: str,
        class_names: List[str],
        promo_code: Optional[str] = None,
        auto_renew: bool = False,
        payment_reference: Optional[str] = None,
    ) -> Dict:
        ...


class LearningSessionPort(Protocol):
    def list_chat_sessions(self, user_id: str) -> List[Dict]:
        ...

    def rename_chat_session(self, user_id: str, session_id: str, title: str) -> Dict:
        ...

    def delete_chat_session(self, user_id: str, session_id: str) -> Dict:
        ...

    def get_session_content(self, user: Dict, session_id: str) -> Dict:
        ...

    def set_session_content(self, user: Dict, session_id: str, content_id: Optional[str]) -> Dict:
        ...

    def list_lesson_sessions(self, user_id: str) -> List[Dict]:
        ...

    def rename_lesson_session(self, user_id: str, session_id: str, title: str) -> Dict:
        ...

    def delete_lesson_session(self, user_id: str, session_id: str) -> Dict:
        ...

    def list_quiz_sessions(self, user_id: str) -> List[Dict]:
        ...

    def rename_quiz_session(self, user_id: str, session_id: str, title: str) -> Dict:
        ...

    def delete_quiz_session(self, user_id: str, session_id: str) -> Dict:
        ...

    def get_latest_quiz(self, user_id: str, session_id: str) -> Optional[Dict]:
        ...

    def list_flashcard_sessions(self, user_id: str) -> List[Dict]:
        ...

    def rename_flashcard_session(self, user_id: str, session_id: str, title: str) -> Dict:
        ...

    def delete_flashcard_session(self, user_id: str, session_id: str) -> Dict:
        ...

    def get_latest_flashcards(self, user_id: str, session_id: str) -> Optional[Dict]:
        ...
