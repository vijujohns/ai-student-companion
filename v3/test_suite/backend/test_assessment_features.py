"""Tests for Assessment API: subject quiz and question paper endpoints."""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(scope="module")
def client():
    import sys

    heavy = [
        "sentence_transformers",
        "faiss",
        "numpy",
        "numpy.core",
        "tqdm",
        "tqdm.auto",
        "pypdf",
        "deep_translator",
        "llama_cpp",
        "openai",
        "docx",
        "python_docx",
    ]
    injected = {}
    for pkg in heavy:
        if pkg not in sys.modules:
            sys.modules[pkg] = MagicMock()
            injected[pkg] = True

    sys.modules["sentence_transformers"].SentenceTransformer = MagicMock(return_value=MagicMock())

    try:
        import app.main as main_module

        with (
            patch.object(main_module, "load_index", return_value=None),
            patch.object(main_module, "load_knowledge_base", return_value=None),
            patch.object(main_module, "init_db", return_value=None),
            patch("threading.Thread"),
        ):
            from app.modules.db import init_db

            init_db()
            # Patch LLM so tests don't need a loaded model
            with patch("app.modules.assessment.generate_response") as mock_llm, \
                 patch("app.modules.assessment.retrieve_chunks") as mock_rag:
                mock_rag.return_value = ["Mocked context chunk"]
                mock_llm.return_value = (
                    '{"questions":['
                    '{"question":"What is photosynthesis?","options":["a","b","c","d"],"answer":"a","explanation":"It is the process","difficulty":"easy","chapter":"Photosynthesis"},'
                    '{"question":"What is respiration?","options":["a","b","c","d"],"answer":"b","explanation":"Energy release","difficulty":"medium","chapter":"Respiration"}'
                    ']}'
                )
                from fastapi.testclient import TestClient

                with TestClient(main_module.app, raise_server_exceptions=True) as c:
                    yield c
    finally:
        for pkg in injected:
            del sys.modules[pkg]


def login(client, email="student@example.com", password="student123"):
    resp = client.post("/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Subject quiz
# ---------------------------------------------------------------------------

class TestSubjectQuiz:

    def test_generate_subject_quiz_returns_questions(self, client):
        """POST /assessment/subject-quiz returns a list of questions."""
        with patch("app.modules.assessment.generate_response") as mock_llm, \
             patch("app.modules.assessment.retrieve_chunks", return_value=["ctx chunk"]):
            mock_llm.return_value = (
                '{"questions":['
                '{"question":"Q1","options":["a","b","c","d"],"answer":"a","explanation":"exp1","difficulty":"easy","chapter":"ch1"},'
                '{"question":"Q2","options":["a","b","c","d"],"answer":"b","explanation":"exp2","difficulty":"medium","chapter":"ch2"}'
                ']}'
            )
            token = login(client)
            resp = client.post(
                "/assessment/subject-quiz",
                json={"subject": "Science", "class_name": "Class 10", "num_questions": 2, "difficulty": "mixed", "mode": "practice"},
                headers=auth(token),
            )
        assert resp.status_code == 200
        body = resp.json()
        questions = body.get("questions") or (body.get("data") or {}).get("questions") or []
        assert len(questions) >= 2

    def test_generate_subject_quiz_has_paper_id(self, client):
        """Generated quiz returns a paper_id for future retrieval."""
        with patch("app.modules.assessment.generate_response") as mock_llm, \
             patch("app.modules.assessment.retrieve_chunks", return_value=["ctx"]):
            mock_llm.return_value = '{"questions":[{"question":"Q1","options":["a","b","c","d"],"answer":"a","explanation":"","difficulty":"easy","chapter":""}]}'
            token = login(client)
            resp = client.post(
                "/assessment/subject-quiz",
                json={"subject": "Mathematics", "num_questions": 1, "difficulty": "easy", "mode": "exam"},
                headers=auth(token),
            )
        assert resp.status_code == 200
        data = resp.json().get("data") or resp.json()
        assert "paper_id" in data

    def test_generate_subject_quiz_invalid_difficulty(self, client):
        """POST /assessment/subject-quiz rejects invalid difficulty."""
        token = login(client)
        resp = client.post(
            "/assessment/subject-quiz",
            json={"subject": "Science", "difficulty": "extreme"},
            headers=auth(token),
        )
        assert resp.status_code == 422

    def test_generate_subject_quiz_invalid_mode(self, client):
        """POST /assessment/subject-quiz rejects invalid mode."""
        token = login(client)
        resp = client.post(
            "/assessment/subject-quiz",
            json={"subject": "Science", "mode": "cheat"},
            headers=auth(token),
        )
        assert resp.status_code == 422

    def test_generate_subject_quiz_requires_subject(self, client):
        """Empty subject is rejected."""
        token = login(client)
        resp = client.post(
            "/assessment/subject-quiz",
            json={"subject": ""},
            headers=auth(token),
        )
        assert resp.status_code == 422

    def test_generate_subject_quiz_unauthenticated(self, client):
        """Unauthenticated request returns 401/403."""
        client.cookies.clear()
        resp = client.post("/assessment/subject-quiz", json={"subject": "Science"})
        assert resp.status_code in (401, 403)

    def test_practice_mode_quiz_contains_mode_field(self, client):
        """Generated quiz result includes the mode field."""
        with patch("app.modules.assessment.generate_response") as mock_llm, \
             patch("app.modules.assessment.retrieve_chunks", return_value=["ctx"]):
            mock_llm.return_value = '{"questions":[{"question":"Q?","options":["a","b","c","d"],"answer":"a","explanation":"","difficulty":"easy","chapter":""}]}'
            token = login(client)
            resp = client.post(
                "/assessment/subject-quiz",
                json={"subject": "History", "num_questions": 1, "mode": "practice"},
                headers=auth(token),
            )
        assert resp.status_code == 200
        data = resp.json().get("data") or resp.json()
        assert data.get("mode") == "practice"


# ---------------------------------------------------------------------------
# Question paper
# ---------------------------------------------------------------------------

class TestQuestionPaper:

    def test_generate_question_paper_has_sections(self, client):
        """POST /assessment/question-paper returns sections list."""
        with patch("app.modules.assessment.generate_response") as mock_llm, \
             patch("app.modules.assessment.retrieve_chunks", return_value=["ctx"]):
            mock_llm.return_value = '{"questions":[{"question":"Q?","options":["a","b","c","d"],"answer":"a","difficulty":"easy"}]}'
            token = login(client)
            resp = client.post(
                "/assessment/question-paper",
                json={"subject": "Physics", "class_name": "Class 11", "total_marks": 20, "difficulty": "medium"},
                headers=auth(token),
            )
        assert resp.status_code == 200
        data = resp.json().get("data") or resp.json()
        assert isinstance(data.get("sections"), list)
        assert len(data["sections"]) > 0

    def test_generate_question_paper_has_paper_id(self, client):
        """Question paper generation returns a paper_id."""
        with patch("app.modules.assessment.generate_response") as mock_llm, \
             patch("app.modules.assessment.retrieve_chunks", return_value=["ctx"]):
            mock_llm.return_value = '{"questions":[{"question":"Q?","answer_key":"k","difficulty":"medium"}]}'
            token = login(client)
            resp = client.post(
                "/assessment/question-paper",
                json={"subject": "Chemistry", "total_marks": 20},
                headers=auth(token),
            )
        assert resp.status_code == 200
        data = resp.json().get("data") or resp.json()
        assert "paper_id" in data

    def test_generate_question_paper_invalid_difficulty(self, client):
        """Invalid difficulty triggers 422."""
        token = login(client)
        resp = client.post(
            "/assessment/question-paper",
            json={"subject": "Math", "difficulty": "super_hard"},
            headers=auth(token),
        )
        assert resp.status_code == 422

    def test_generate_question_paper_marks_clamp(self, client):
        """total_marks < 10 triggers 422 (Pydantic ge=10 constraint)."""
        token = login(client)
        resp = client.post(
            "/assessment/question-paper",
            json={"subject": "Math", "total_marks": 5},
            headers=auth(token),
        )
        assert resp.status_code == 422

    def test_generate_question_paper_unauthenticated(self, client):
        """Unauthenticated request returns 401/403."""
        client.cookies.clear()
        resp = client.post("/assessment/question-paper", json={"subject": "Science"})
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# List / retrieve papers
# ---------------------------------------------------------------------------

class TestAssessmentPaperRetrieval:

    def test_list_papers_returns_list(self, client):
        """GET /assessment/papers returns a list (possibly empty)."""
        token = login(client)
        resp = client.get("/assessment/papers", headers=auth(token))
        assert resp.status_code == 200
        data = resp.json().get("data") or resp.json()
        assert isinstance(data.get("papers"), list)

    def test_list_papers_filtered_by_type(self, client):
        """GET /assessment/papers?paper_type=SUBJECT_QUIZ filters results."""
        token = login(client)
        resp = client.get("/assessment/papers?paper_type=SUBJECT_QUIZ", headers=auth(token))
        assert resp.status_code == 200

    def test_get_paper_not_found(self, client):
        """GET /assessment/papers/{id} returns 404 for unknown ID."""
        token = login(client)
        resp = client.get("/assessment/papers/99999999", headers=auth(token))
        assert resp.status_code == 404

    def test_get_paper_persisted_after_generation(self, client):
        """Paper generated can be retrieved by ID."""
        with patch("app.modules.assessment.generate_response") as mock_llm, \
             patch("app.modules.assessment.retrieve_chunks", return_value=["ctx"]):
            mock_llm.return_value = '{"questions":[{"question":"Q?","options":["a","b","c","d"],"answer":"a","explanation":"","difficulty":"easy","chapter":""}]}'
            token = login(client)
            gen = client.post(
                "/assessment/subject-quiz",
                json={"subject": "Biology", "num_questions": 1},
                headers=auth(token),
            )
        assert gen.status_code == 200
        paper_id = (gen.json().get("data") or gen.json()).get("paper_id")
        assert paper_id
        get_resp = client.get(f"/assessment/papers/{paper_id}", headers=auth(token))
        assert get_resp.status_code == 200
        fetched = (get_resp.json().get("data") or get_resp.json()).get("paper")
        assert fetched is not None
        assert fetched["paper_id"] == paper_id
        assert len(fetched.get("questions") or []) >= 1

    def test_list_papers_include_summary_counts(self, client):
        """Assessment history summaries include counts for richer UI cards."""
        token = login(client)

        with patch("app.modules.assessment.generate_response") as mock_llm, \
             patch("app.modules.assessment.retrieve_chunks", return_value=["ctx"]):
            mock_llm.return_value = '{"questions":[{"question":"Quiz Q1","options":["a","b","c","d"],"answer":"a","explanation":"","difficulty":"easy","chapter":""}]}'
            quiz_resp = client.post(
                "/assessment/subject-quiz",
                json={"subject": "Science", "num_questions": 1},
                headers=auth(token),
            )
            assert quiz_resp.status_code == 200

        with patch("app.modules.assessment.generate_response") as mock_llm, \
             patch("app.modules.assessment.retrieve_chunks", return_value=["ctx"]):
            mock_llm.return_value = '{"questions":[{"question":"Paper Q1","answer_key":"Model answer","difficulty":"medium"}]}'
            paper_resp = client.post(
                "/assessment/question-paper",
                json={"subject": "History", "total_marks": 20},
                headers=auth(token),
            )
            assert paper_resp.status_code == 200

        resp = client.get("/assessment/papers", headers=auth(token))
        assert resp.status_code == 200
        papers = ((resp.json().get("data") or resp.json()).get("papers") or [])
        summaries = {paper["paper_type"]: paper for paper in papers if paper.get("paper_type") in {"SUBJECT_QUIZ", "QUESTION_PAPER"}}

        assert summaries["SUBJECT_QUIZ"]["question_count"] >= 1
        assert summaries["QUESTION_PAPER"]["section_count"] >= 1
        assert summaries["QUESTION_PAPER"]["total_marks"] >= 10

    def test_record_attempt_updates_history_summary(self, client):
        """Saving an assessment attempt should enrich history with best/latest score info."""
        with patch("app.modules.assessment.generate_response") as mock_llm, \
             patch("app.modules.assessment.retrieve_chunks", return_value=["ctx"]):
            mock_llm.return_value = '{"questions":[{"question":"Q1","options":["a","b","c","d"],"answer":"a","explanation":"","difficulty":"easy","chapter":""}]}'
            token = login(client)
            gen = client.post(
                "/assessment/subject-quiz",
                json={"subject": "Biology", "num_questions": 1, "mode": "exam"},
                headers=auth(token),
            )

        assert gen.status_code == 200
        paper_id = (gen.json().get("data") or gen.json()).get("paper_id")
        assert paper_id

        save_resp = client.post(
            f"/assessment/papers/{paper_id}/attempt",
            json={"correct_count": 1, "total_questions": 1, "score_pct": 100},
            headers=auth(token),
        )
        assert save_resp.status_code == 200
        attempt_summary = ((save_resp.json().get("data") or save_resp.json()).get("attempt_summary") or {})
        assert attempt_summary["attempt_count"] == 1
        assert attempt_summary["best_score_pct"] == 100
        assert attempt_summary["last_score_pct"] == 100
        assert attempt_summary["last_attempted_at"]
        assert attempt_summary["recent_scores"] == [100]

        follow_up_resp = client.post(
            f"/assessment/papers/{paper_id}/attempt",
            json={"correct_count": 0, "total_questions": 1, "score_pct": 0},
            headers=auth(token),
        )
        assert follow_up_resp.status_code == 200
        updated_summary = ((follow_up_resp.json().get("data") or follow_up_resp.json()).get("attempt_summary") or {})
        assert updated_summary["attempt_count"] == 2
        assert updated_summary["best_score_pct"] == 100
        assert updated_summary["last_score_pct"] == 0
        assert updated_summary["recent_scores"][:2] == [0, 100]

        history_resp = client.get("/assessment/papers", headers=auth(token))
        assert history_resp.status_code == 200
        papers = ((history_resp.json().get("data") or history_resp.json()).get("papers") or [])
        saved = next(paper for paper in papers if paper["paper_id"] == paper_id)
        assert saved["attempt_count"] == 2
        assert saved["best_score_pct"] == 100
        assert saved["last_score_pct"] == 0
        assert saved["last_attempted_at"]
        assert saved["recent_scores"][:2] == [0, 100]

        dashboard_resp = client.get("/progress/dashboard", headers=auth(token))
        assert dashboard_resp.status_code == 200
        dashboard = dashboard_resp.json().get("data") or dashboard_resp.json()
        assessment_summary = dashboard["assessment_summary"]
        assert assessment_summary["attempt_count"] >= 2
        assert assessment_summary["best_score_pct"] == 100
        assert assessment_summary["latest_score_pct"] == 0
        assert 0 <= assessment_summary["average_score_pct"] <= 100
        assert assessment_summary["recent_scores"][:2] == [0, 100]

    def test_record_attempt_unknown_paper_returns_404(self, client):
        token = login(client)
        resp = client.post(
            "/assessment/papers/99999999/attempt",
            json={"correct_count": 0, "total_questions": 1, "score_pct": 0},
            headers=auth(token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Schema tests (unit level)
# ---------------------------------------------------------------------------

class TestAssessmentSchemas:

    def test_subject_quiz_request_valid(self):
        from app.schemas.request import SubjectQuizRequest
        req = SubjectQuizRequest(subject="Science", difficulty="easy", mode="practice", num_questions=5)
        assert req.subject == "Science"
        assert req.difficulty == "easy"
        assert req.mode == "practice"

    def test_subject_quiz_request_invalid_difficulty(self):
        from app.schemas.request import SubjectQuizRequest
        import pytest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SubjectQuizRequest(subject="Science", difficulty="extreme")

    def test_subject_quiz_request_invalid_mode(self):
        from app.schemas.request import SubjectQuizRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SubjectQuizRequest(subject="Science", mode="battlefield")

    def test_question_paper_request_valid(self):
        from app.schemas.request import QuestionPaperRequest
        req = QuestionPaperRequest(subject="Math", total_marks=40, difficulty="mixed")
        assert req.total_marks == 40

    def test_question_paper_request_low_marks_rejected(self):
        from app.schemas.request import QuestionPaperRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            QuestionPaperRequest(subject="Math", total_marks=5)

    def test_question_paper_request_custom_sections(self):
        from app.schemas.request import QuestionPaperRequest
        sections = [{"name": "Section A", "marks_per_q": 2, "count": 5}]
        req = QuestionPaperRequest(subject="History", sections=sections)
        assert req.sections == sections

    def test_assessment_attempt_request_rejects_zero_total(self):
        from app.schemas.request import AssessmentAttemptRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AssessmentAttemptRequest(correct_count=1, total_questions=0, score_pct=100)
