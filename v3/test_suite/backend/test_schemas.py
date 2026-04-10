"""
Test Pydantic Schema Validation (Issue #7)
"""

import pytest
from pydantic import ValidationError
from app.schemas.request import (
    LoginRequest, AskRequest, RenameSessionRequest, SetSessionContentRequest,
    LessonPlanCreateRequest, LessonProgressRequest, QuizGenerateRequest,
    QuizSubmitRequest, ArtifactGenerateRequest, SubscriptionActivateRequest
)
from app.modules.flashcards import FlashcardRequest


class TestLoginRequestValidation:
    """Test LoginRequest schema validation"""
    
    def test_valid_login_request(self):
        """Valid login request should pass"""
        req = LoginRequest(email="student@example.com", password="password123")
        assert req.email == "student@example.com"
        assert req.password == "password123"
    
    def test_login_missing_email(self):
        """Missing email should fail"""
        with pytest.raises(ValidationError):
            LoginRequest(password="password123")
    
    def test_login_missing_password(self):
        """Missing password should fail"""
        with pytest.raises(ValidationError):
            LoginRequest(email="student@example.com")
    
    def test_login_empty_email(self):
        """Empty email should fail"""
        with pytest.raises(ValidationError):
            LoginRequest(email="", password="password123")
    
    def test_login_empty_password(self):
        """Empty password should fail"""
        with pytest.raises(ValidationError):
            LoginRequest(email="student@example.com", password="")


class TestAskRequestValidation:
    """Test AskRequest schema validation"""
    
    def test_valid_ask_request(self):
        """Valid ask request should pass"""
        req = AskRequest(query="What is photosynthesis?")
        assert req.query == "What is photosynthesis?"
        assert req.session_id is None
        assert req.model_name is None
    
    def test_ask_with_session_and_model(self):
        """Ask with session_id and model_name should pass"""
        req = AskRequest(
            query="Explain gravity",
            session_id="uuid-123",
            model_name="tinyllama"
        )
        assert req.query == "Explain gravity"
        assert req.session_id == "uuid-123"
        assert req.model_name == "tinyllama"

    def test_ask_accepts_content_id(self):
        req = AskRequest(query="Explain gravity", content_id="upload:7")
        assert req.content_id == "upload:7"
    
    def test_ask_missing_query(self):
        """Missing query should fail"""
        with pytest.raises(ValidationError):
            AskRequest()
    
    def test_ask_empty_query(self):
        """Empty query should fail"""
        with pytest.raises(ValidationError):
            AskRequest(query="")
    
    def test_ask_query_too_long(self):
        """Query exceeding max length should fail"""
        long_query = "x" * 5001  # Exceeds 5000 char limit
        with pytest.raises(ValidationError):
            AskRequest(query=long_query)


class TestRenameSessionRequestValidation:
    """Test RenameSessionRequest schema validation"""
    
    def test_valid_rename_request(self):
        """Valid rename request should pass"""
        req = RenameSessionRequest(title="My New Title")
        assert req.title == "My New Title"
    
    def test_rename_missing_title(self):
        """Missing title should fail"""
        with pytest.raises(ValidationError):
            RenameSessionRequest()
    
    def test_rename_empty_title(self):
        """Empty title should fail"""
        with pytest.raises(ValidationError):
            RenameSessionRequest(title="")


class TestSetSessionContentRequestValidation:
    def test_accepts_content_id(self):
        req = SetSessionContentRequest(content_id="upload:7")
        assert req.content_id == "upload:7"

    def test_rejects_unknown_field_path(self):
        with pytest.raises(ValidationError):
            SetSessionContentRequest(path="Class 8/English-1/Text Books/Chapter 1.pdf")

    def test_allows_clear_payload(self):
        req = SetSessionContentRequest()
        assert req.content_id is None


class TestLessonProgressRequestValidation:
    """Test LessonProgressRequest schema validation"""
    
    def test_valid_progress_request(self):
        """Valid progress request should pass"""
        req = LessonProgressRequest(
            session_id="uuid-123",
            step_id=1,
            status="completed"
        )
        assert req.session_id == "uuid-123"
        assert req.step_id == 1
        assert req.status == "completed"
    
    def test_progress_negative_step_id(self):
        """Negative step_id should fail"""
        with pytest.raises(ValidationError):
            LessonProgressRequest(
                session_id="uuid-123",
                step_id=-1,
                status="completed"
            )
    
    def test_progress_missing_fields(self):
        """Missing required fields should fail"""
        with pytest.raises(ValidationError):
            LessonProgressRequest(session_id="uuid-123")


class TestQuizSubmitRequestValidation:
    """Test QuizSubmitRequest schema validation"""
    
    def test_valid_quiz_submit(self):
        """Valid quiz submit should pass"""
        req = QuizSubmitRequest(
            session_id="uuid-123",
            answers={"q1": "A", "q2": "B", "q3": "C"}
        )
        assert req.session_id == "uuid-123"
        assert req.answers["q1"] == "A"
    
    def test_quiz_submit_empty_answers(self):
        """Empty answers dict should still pass (user may skip)"""
        req = QuizSubmitRequest(
            session_id="uuid-123",
            answers={}
        )
        assert req.answers == {}
    
    def test_quiz_submit_missing_answers(self):
        """Missing answers field should fail"""
        with pytest.raises(ValidationError):
            QuizSubmitRequest(session_id="uuid-123")


class TestQuizAndArtifactContextValidation:
    def test_quiz_generate_allows_optional_context(self):
        req = QuizGenerateRequest(
            session_id="uuid-123",
            chapter="Photosynthesis",
            quiz_context="Focus on recall and tricky MCQs",
            content_id="upload:7",
        )
        assert req.quiz_context == "Focus on recall and tricky MCQs"
        assert req.content_id == "upload:7"

    def test_artifact_generate_request_allows_empty_payload(self):
        req = ArtifactGenerateRequest()
        assert req.context is None
        assert req.content_id is None

    def test_artifact_generate_request_accepts_selected_content(self):
        req = ArtifactGenerateRequest(context="Focus on the selected card", content_id="kb:kerala")
        assert req.context == "Focus on the selected card"
        assert req.content_id == "kb:kerala"

    def test_artifact_generate_request_rejects_long_context(self):
        with pytest.raises(ValidationError):
            ArtifactGenerateRequest(context="x" * 1001)


class TestFlashcardRequestValidation:
    def test_valid_flashcard_request(self):
        req = FlashcardRequest(class_name="Class 8", subject="English-1", content_type="Notes")
        assert req.class_name == "Class 8"

    def test_rejects_unknown_field(self):
        """extra='forbid' should reject unknown fields."""
        with pytest.raises(ValidationError):
            FlashcardRequest(class_name="Class 8", subject="English-1", content_type="Notes", unknown_field="bad")


class TestSubscriptionActivateRequestValidation:
    def test_valid_activate_request(self):
        req = SubscriptionActivateRequest(
            class_names=["Class 8"],
            promo_code="WELCOME10",
            auto_renew=True,
            payment_reference="txn-111",
        )
        assert req.class_names == ["Class 8"]
        assert req.payment_reference == "txn-111"

    def test_activate_request_rejects_blank_classes(self):
        with pytest.raises(ValidationError):
            SubscriptionActivateRequest(class_names=["   "], auto_renew=False)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
