import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(scope="module")
def client():
    heavy = [
        "sentence_transformers", "faiss", "numpy", "numpy.core",
        "tqdm", "tqdm.auto", "pypdf", "deep_translator",
        "llama_cpp", "openai", "docx", "python_docx",
    ]
    injected = {}
    for pkg in heavy:
        if pkg not in sys.modules:
            sys.modules[pkg] = MagicMock()
            injected[pkg] = True

    st_mock = sys.modules["sentence_transformers"]
    st_mock.SentenceTransformer = MagicMock(return_value=MagicMock())

    try:
        import app.main as main_module
        from fastapi.testclient import TestClient

        with (
            patch.object(main_module, "load_index", return_value=None),
            patch.object(main_module, "load_knowledge_base", return_value=None),
            patch.object(main_module, "init_db", return_value=None),
            patch("threading.Thread"),
        ):
            from app.modules.db import init_db
            init_db()
            with TestClient(main_module.app, raise_server_exceptions=True) as c:
                yield c
    finally:
        for pkg in injected:
            del sys.modules[pkg]


@pytest.fixture(autouse=True)
def clear_cookies(client):
    client.cookies.clear()


def _register(client, email: str, role: str):
    return client.post(
        "/register",
        json={
            "first_name": role.capitalize(),
            "last_name": "User",
            "email": email,
            "dob": "1995-01-01",
            "password": "pass1234",
            "role": role,
        },
    )


def _login(client, email: str, password: str = "pass1234"):
    response = client.post("/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str):
    return {"Authorization": f"Bearer {token}"}


class TestRoleRegistration:
    def test_register_teacher_role(self, client):
        email = "teacher_roles_test@example.com"
        response = _register(client, email, "teacher")
        assert response.status_code in (200, 409)

        token = _login(client, email)
        session = client.get("/auth/session", headers=_auth(token))
        assert session.status_code == 200
        assert session.json()["role"] == "teacher"

    def test_register_parent_role(self, client):
        email = "parent_roles_test@example.com"
        response = _register(client, email, "parent")
        assert response.status_code in (200, 409)

        token = _login(client, email)
        session = client.get("/auth/session", headers=_auth(token))
        assert session.status_code == 200
        assert session.json()["role"] == "parent"


class TestRelationshipAndCollaboration:
    def test_student_cannot_link_student(self, client):
        token = _login(client, "student@example.com", "student123")
        response = client.post(
            "/relationships/link-student",
            headers=_auth(token),
            json={"student_email": "student@example.com"},
        )
        assert response.status_code == 403

    def test_teacher_link_student_and_roster(self, client):
        teacher_email = "teacher_link_test@example.com"
        _register(client, teacher_email, "teacher")
        teacher_token = _login(client, teacher_email)

        response = client.post(
            "/relationships/link-student",
            headers=_auth(teacher_token),
            json={"student_email": "student@example.com", "relation_label": "Class Teacher"},
        )
        assert response.status_code == 200
        assert response.json()["relation_role"] == "teacher"

        roster = client.get("/relationships/my-students", headers=_auth(teacher_token))
        assert roster.status_code == 200
        emails = [item["email"] for item in roster.json()["students"]]
        assert "student@example.com" in emails

    def test_teacher_can_unlink_own_student_relationship(self, client):
        teacher_email = "teacher_unlink_test@example.com"
        _register(client, teacher_email, "teacher")
        teacher_token = _login(client, teacher_email)

        link_response = client.post(
            "/relationships/link-student",
            headers=_auth(teacher_token),
            json={"student_email": "student@example.com", "relation_label": "Temporary Coach"},
        )
        assert link_response.status_code == 200
        assert link_response.json()["linking_mode"] == "direct_existing_student"
        assert link_response.json()["approval_required"] is False

        unlink_response = client.delete(
            "/relationships/students/student@example.com",
            headers=_auth(teacher_token),
        )
        assert unlink_response.status_code == 200
        assert unlink_response.json()["status"] == "unlinked"

        roster = client.get("/relationships/my-students", headers=_auth(teacher_token))
        assert roster.status_code == 200
        assert "student@example.com" not in [item["email"] for item in roster.json()["students"]]

    def test_student_can_view_my_mentors_after_link(self, client):
        token = _login(client, "student@example.com", "student123")
        response = client.get("/relationships/my-mentors", headers=_auth(token))
        assert response.status_code == 200
        assert any(item["role"] == "teacher" for item in response.json()["mentors"])

    def test_linked_teacher_can_view_student_progress(self, client):
        teacher_token = _login(client, "teacher_link_test@example.com")
        response = client.get("/students/student@example.com/progress", headers=_auth(teacher_token))
        assert response.status_code == 200
        body = response.json()
        assert body["student_username"] == "student"
        assert "dashboard" in body
        assert "insights" in body
        assert "study_plan" in body
        assert set(body["dashboard"].keys()) >= {"assignments"}
        assert set(body["insights"].keys()) == {"headline", "recommendations", "badges", "notifications"}
        assert set(body["study_plan"].keys()) >= {"headline", "schedule", "goal_summary", "targets", "history"}

    def test_unlinked_teacher_cannot_view_progress(self, client):
        other_teacher_email = "teacher_unlinked_test@example.com"
        _register(client, other_teacher_email, "teacher")
        token = _login(client, other_teacher_email)

        response = client.get("/students/student@example.com/progress", headers=_auth(token))
        assert response.status_code == 403

    def test_teacher_can_assign_task_and_student_can_view_it(self, client):
        teacher_token = _login(client, "teacher_link_test@example.com")

        create_assignment = client.post(
            "/students/student@example.com/assignments",
            headers=_auth(teacher_token),
            json={
                "title": "Practice Science quiz",
                "description": "Use one short quiz to strengthen optics recall.",
                "action_tab": "quiz",
                "cta_label": "Open Assigned Quiz",
                "chapter_hint": "Science",
                "context_hint": "Use one short quiz to strengthen optics recall.",
            },
        )
        assert create_assignment.status_code == 200
        assignment_id = create_assignment.json()["assignment_id"]

        student_token = _login(client, "student@example.com", "student123")
        assignment_list = client.get("/students/student@example.com/assignments", headers=_auth(student_token))
        assert assignment_list.status_code == 200
        assert any(item["id"] == assignment_id and item["action_tab"] == "quiz" for item in assignment_list.json()["assignments"])

        progress = client.get("/students/student@example.com/progress", headers=_auth(teacher_token))
        assert progress.status_code == 200
        assert any(item["id"] == assignment_id for item in progress.json()["dashboard"]["assignments"])

    def test_assignment_collection_supports_pagination(self, client):
        teacher_email = "teacher_pagination_test@example.com"
        _register(client, teacher_email, "teacher")
        teacher_token = _login(client, teacher_email)

        link_response = client.post(
            "/relationships/link-student",
            headers=_auth(teacher_token),
            json={"student_email": "student@example.com", "relation_label": "Pagination Class"},
        )
        assert link_response.status_code == 200

        for index in range(3):
            response = client.post(
                "/students/student/assignments",
                headers=_auth(teacher_token),
                json={
                    "title": f"Pagination Task {index}",
                    "description": "Practice pagination-safe assignment loading.",
                    "action_tab": "lesson",
                    "cta_label": "Open Lesson",
                },
            )
            assert response.status_code == 200

        page = client.get("/students/student/assignments?limit=2&offset=0", headers=_auth(teacher_token))
        assert page.status_code == 200
        body = page.json()
        assert len(body["assignments"]) == 2
        assert body["pagination"]["limit"] == 2
        assert body["pagination"]["offset"] == 0
        assert body["pagination"]["total"] >= 3
        assert body["pagination"]["has_more"] is True

    def test_assignment_can_be_completed_and_deleted(self, client):
        teacher_token = _login(client, "teacher_link_test@example.com")
        create_assignment = client.post(
            "/students/student@example.com/assignments",
            headers=_auth(teacher_token),
            json={
                "title": "Retry Science assessment",
                "description": "Complete one exam-style checkpoint by Friday.",
                "action_tab": "assessment",
                "cta_label": "Open Assigned Assessment",
                "chapter_hint": "Science",
                "context_hint": "Complete one exam-style checkpoint by Friday.",
                "due_label": "2026-04-10",
            },
        )
        assert create_assignment.status_code == 200
        assignment_id = create_assignment.json()["assignment_id"]

        student_token = _login(client, "student@example.com", "student123")
        complete_assignment = client.put(
            f"/students/student@example.com/assignments/{assignment_id}",
            headers=_auth(student_token),
            json={"status": "completed"},
        )
        assert complete_assignment.status_code == 200
        assert complete_assignment.json()["status"] == "completed"

        update_assignment = client.put(
            f"/students/student@example.com/assignments/{assignment_id}",
            headers=_auth(teacher_token),
            json={"title": "Retry Science assessment again", "due_label": "2026-04-12"},
        )
        assert update_assignment.status_code == 200
        assert update_assignment.json()["due_label"] == "2026-04-12"

        delete_assignment = client.delete(
            f"/students/student@example.com/assignments/{assignment_id}",
            headers=_auth(teacher_token),
        )
        assert delete_assignment.status_code == 200

        assignment_list = client.get("/students/student@example.com/assignments", headers=_auth(teacher_token))
        assert assignment_list.status_code == 200
        assert all(item["id"] != assignment_id for item in assignment_list.json()["assignments"])

    def test_overdue_assignment_surfaces_high_priority_notification(self, client):
        teacher_token = _login(client, "teacher_link_test@example.com")
        create_assignment = client.post(
            "/students/student@example.com/assignments",
            headers=_auth(teacher_token),
            json={
                "title": "Finish Algebra worksheet",
                "description": "This mentor task is overdue and needs attention.",
                "action_tab": "lesson",
                "cta_label": "Open Assigned Lesson",
                "chapter_hint": "Math",
                "context_hint": "This mentor task is overdue and needs attention.",
                "due_label": "2000-01-01",
            },
        )
        assert create_assignment.status_code == 200

        progress = client.get("/students/student@example.com/progress", headers=_auth(teacher_token))
        assert progress.status_code == 200
        notifications = progress.json()["insights"]["notifications"]
        overdue_notification = next((item for item in notifications if item.get("title") == "Overdue assignment"), None)
        assert overdue_notification is not None
        assert overdue_notification["severity"] == "high"
        assert "2000-01-01" in overdue_notification["message"]

    def test_collaboration_notes_visibility_between_teacher_parent_student(self, client):
        parent_email = "parent_link_test@example.com"
        _register(client, parent_email, "parent")
        parent_token = _login(client, parent_email)

        # Parent link to same student.
        link_parent = client.post(
            "/relationships/link-student",
            headers=_auth(parent_token),
            json={"student_email": "student@example.com", "relation_label": "Guardian"},
        )
        assert link_parent.status_code == 200

        teacher_token = _login(client, "teacher_link_test@example.com")

        # Teacher creates a guardians-only note.
        create_note = client.post(
            "/collaboration/notes",
            headers=_auth(teacher_token),
            json={
                "student_username": "student@example.com",
                "note_text": "Needs revision for algebra basics.",
                "visibility": "guardians",
            },
        )
        assert create_note.status_code == 200

        # Linked guardians should see guardian-only notes.
        parent_notes = client.get("/students/student@example.com/notes", headers=_auth(parent_token))
        assert parent_notes.status_code == 200
        assert any("algebra basics" in n["note_text"] for n in parent_notes.json()["notes"])

        # Student can view all notes attached to their profile.
        student_token = _login(client, "student@example.com", "student123")
        student_notes = client.get("/students/student@example.com/notes", headers=_auth(student_token))
        assert student_notes.status_code == 200
        assert any("algebra basics" in n["note_text"] for n in student_notes.json()["notes"])

    def test_note_author_can_update_note(self, client):
        teacher_token = _login(client, "teacher_link_test@example.com")
        create_note = client.post(
            "/collaboration/notes",
            headers=_auth(teacher_token),
            json={
                "student_username": "student@example.com",
                "note_text": "Review algebra confidence this week.",
                "visibility": "all",
            },
        )
        assert create_note.status_code == 200
        note_id = create_note.json()["note_id"]

        update_note = client.put(
            f"/students/student@example.com/notes/{note_id}",
            headers=_auth(teacher_token),
            json={"note_text": "Review algebra and geometry confidence this week.", "visibility": "guardians"},
        )
        assert update_note.status_code == 200
        assert "geometry confidence" in update_note.json()["note_text"]
        assert update_note.json()["visibility"] == "guardians"

        notes_after_update = client.get("/students/student@example.com/notes", headers=_auth(teacher_token))
        assert notes_after_update.status_code == 200
        assert any(note["id"] == note_id and "geometry confidence" in note["note_text"] for note in notes_after_update.json()["notes"])

    def test_note_author_can_delete_note(self, client):
        teacher_token = _login(client, "teacher_link_test@example.com")
        create_note = client.post(
            "/collaboration/notes",
            headers=_auth(teacher_token),
            json={
                "student_username": "student@example.com",
                "note_text": "Delete this mentor note after review.",
                "visibility": "all",
            },
        )
        assert create_note.status_code == 200
        note_id = create_note.json()["note_id"]

        delete_note = client.delete(
            f"/students/student@example.com/notes/{note_id}",
            headers=_auth(teacher_token),
        )
        assert delete_note.status_code == 200

        notes_after_delete = client.get("/students/student@example.com/notes", headers=_auth(teacher_token))
        assert notes_after_delete.status_code == 200
        assert all(note["id"] != note_id for note in notes_after_delete.json()["notes"])
