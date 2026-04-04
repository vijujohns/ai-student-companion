"""
Comprehensive tests for lesson_plan module.
Tests all major functions including lesson plan generation, session management,
progress tracking, and card operations.
"""

import json
import uuid
from datetime import datetime, UTC
from unittest.mock import patch, MagicMock
import pytest

from app.modules.lesson_plan import (
    default_steps,
    _extract_json_from_text,
    _steps_from_llm_text,
    _default_steps_with_content,
    _build_adaptive_steps_with_content,
    _is_too_extractive,
    _rewrite_steps_abstractive,
    _normalize_steps,
    _save_lesson_cards,
    generate_lesson_plan,
    list_lesson_sessions,
    rename_lesson_session,
    delete_lesson_session,
    get_lesson_plan,
    get_lesson_plan_cards,
    complete_lesson_card,
    get_card_for_user,
    update_step_progress,
    get_next_step,
    reset_lesson_progress,
)


class TestDefaultSteps:
    def test_default_steps_returns_five_steps(self):
        """Test that default_steps returns exactly 5 steps."""
        steps = default_steps()
        assert len(steps) == 5
        assert steps[0]["title"] == "Introduction"
        assert steps[4]["title"] == "Revision"

    def test_default_steps_have_required_fields(self):
        """Test all default steps have required fields."""
        steps = default_steps()
        for step in steps:
            assert "id" in step
            assert "title" in step
            assert "type" in step
            assert "status" in step
            assert "content" in step
            assert "bullets" in step
            assert "numbered" in step
            assert step["status"] == "pending"
            assert step["content"] == ""


class TestExtractJsonFromText:
    def test_extract_json_direct_parse(self):
        """Test extracting JSON when directly parseable."""
        text = '{"steps": [{"title": "Step 1"}]}'
        result = _extract_json_from_text(text)
        assert result is not None
        assert "steps" in result
        assert result["steps"][0]["title"] == "Step 1"

    def test_extract_json_from_fenced_block(self):
        """Test extracting JSON from fenced code block."""
        text = """Some text before
```json
{"steps": [{"title": "Step 1"}]}
```
Some text after"""
        result = _extract_json_from_text(text)
        assert result is not None
        assert "steps" in result

    def test_extract_json_invalid_json(self):
        """Test that invalid JSON returns None."""
        result = _extract_json_from_text("{invalid json}")
        assert result is None

    def test_extract_json_none_input(self):
        """Test that None input returns None."""
        result = _extract_json_from_text(None)
        assert result is None

    def test_extract_json_empty_string(self):
        """Test that empty string returns None."""
        result = _extract_json_from_text("")
        assert result is None


class TestStepsFromLlmText:
    def test_parse_numbered_sections(self):
        """Test parsing numbered section format."""
        text = """
1. Introduction
2. Key Concepts
3. Examples
"""
        chunks = ["chunk1", "chunk2", "chunk3"]
        steps = _steps_from_llm_text(text, chunks)
        assert len(steps) >= 2
        assert steps[0]["title"] == "Introduction"

    def test_parse_markdown_headers(self):
        """Test parsing markdown headers."""
        text = """
# Introduction
# Key Concepts  
# Examples
"""
        chunks = ["chunk1", "chunk2", "chunk3"]
        steps = _steps_from_llm_text(text, chunks)
        assert len(steps) >= 2

    def test_insufficient_sections_returns_empty(self):
        """Test that fewer than 2 sections returns empty list."""
        text = "# Only One Section"
        chunks = ["chunk1"]
        steps = _steps_from_llm_text(text, chunks)
        assert steps == []

    def test_step_limit_of_eight(self):
        """Test that at most 8 steps are returned."""
        text = "\n".join([f"{i}. Step {i}" for i in range(1, 15)])
        chunks = ["chunk"] * 14
        steps = _steps_from_llm_text(text, chunks)
        assert len(steps) <= 8


class TestDefaultStepsWithContent:
    def test_creates_five_standard_steps(self):
        """Test that standard 5-step structure is created."""
        chunks = ["content1", "content2", "content3", "content4", "content5"]
        steps = _default_steps_with_content(chunks, "Chapter 1")
        assert len(steps) == 5
        assert steps[0]["title"] == "Introduction"
        assert steps[4]["title"] == "Summary & Revision"

    def test_distributes_chunks_across_steps(self):
        """Test that chunks are distributed across steps."""
        chunks = ["chunk1", "chunk2", "chunk3", "chunk4", "chunk5"]
        steps = _default_steps_with_content(chunks, "Chapter 1")
        for step in steps:
            assert step["content"] != ""

    def test_empty_chunks_provides_fallback_content(self):
        """Test that empty chunks provides helpful fallback."""
        steps = _default_steps_with_content([], "Chapter 1")
        for step in steps:
            assert "Chapter 1" in step["content"]


class TestNormalizeSteps:
    def test_normalize_ensures_proper_types(self):
        """Test that normalize converts all fields to proper types."""
        steps = [
            {"id": "1", "title": 123, "type": None, "status": "pending", "content": 456},
        ]
        normalized = _normalize_steps(steps)
        assert isinstance(normalized[0]["id"], int)
        assert isinstance(normalized[0]["title"], str)
        assert isinstance(normalized[0]["type"], str)
        assert isinstance(normalized[0]["content"], str)

    def test_normalize_preserves_structured_lists(self):
        steps = [
            {
                "id": 1,
                "title": "Intro",
                "content": "Summary",
                "bullets": ["Point one", "Point two"],
                "numbered": ["First step"],
            }
        ]

        normalized = _normalize_steps(steps)
        assert normalized[0]["bullets"] == ["Point one.", "Point two."]
        assert normalized[0]["numbered"] == ["First step."]

    def test_normalize_adds_missing_fields(self):
        """Test that normalize adds missing fields with defaults."""
        steps = [{}]
        normalized = _normalize_steps(steps)
        assert "id" in normalized[0]
        assert "title" in normalized[0]
        assert "status" in normalized[0] and normalized[0]["status"] == "pending"


class TestGenerateLessonPlan:
    @patch("app.modules.lesson_plan.retrieve_chunks")
    @patch("app.modules.lesson_plan.generate_response")
    def test_generate_lesson_plan_with_valid_llm_response(self, mock_generate, mock_retrieve):
        """Test lesson plan generation with valid LLM JSON response."""
        mock_retrieve.return_value = ["chunk1", "chunk2"]
        llm_response = json.dumps({
            "steps": [
                {"title": "Intro", "type": "concept", "content": "content1", "bullets": ["b1"], "numbered": []},
                {"title": "Key Points", "type": "concept", "content": "content2", "bullets": ["b2"], "numbered": []},
            ]
        })
        mock_generate.return_value = llm_response

        plan = generate_lesson_plan("user1", "session1", "Chapter 1")

        assert plan is not None
        assert plan["chapter"] == "Chapter 1"
        assert len(plan["steps"]) == 2
        assert plan["session_id"] == "session1"
        assert "lesson_plan_id" in plan
        assert plan["steps"][0]["bullets"] == ["b1."]

    @patch("app.modules.lesson_plan.retrieve_chunks")
    @patch("app.modules.lesson_plan.generate_response")
    def test_generate_lesson_plan_with_None_session_id(self, mock_generate, mock_retrieve):
        """Test that None session_id generates a new UUID."""
        mock_retrieve.return_value = ["chunk1"]
        mock_generate.return_value = json.dumps({"steps": []})

        plan = generate_lesson_plan("user1", None, "Chapter 1")

        assert plan["session_id"] is not None
        # Should be a valid UUID string
        try:
            uuid.UUID(plan["session_id"])
            valid_uuid = True
        except ValueError:
            valid_uuid = False
        assert valid_uuid

    @patch("app.modules.lesson_plan.retrieve_chunks")
    @patch("app.modules.lesson_plan.generate_response")
    def test_generate_lesson_plan_fallback_to_default_steps(self, mock_generate, mock_retrieve):
        """Test fallback to default steps when LLM fails."""
        mock_retrieve.return_value = []
        mock_generate.side_effect = Exception("LLM error")

        plan = generate_lesson_plan("user1", "session1", "Chapter 1")

        assert len(plan["steps"]) == 5
        assert plan["steps"][0]["title"] == "Introduction"

    def test_adaptive_fallback_generates_structured_content(self):
        chunks = [
            "Kerala has varied landscapes including hills, backwaters, and coastal plains.",
            "The state is known for festivals, literacy, and traditional arts.",
            "People also study industries, transport, and cultural practices across districts.",
        ]

        steps = _build_adaptive_steps_with_content(chunks, "Kerala")

        assert len(steps) >= 1
        assert any(step["content"] for step in steps)
        assert any(step["bullets"] or step["numbered"] for step in steps)


class TestAbstractiveRewrite:
    def test_is_too_extractive_detects_heavy_copy(self):
        source = "Kerala has rivers, backwaters, forests, and coastal plains with rich biodiversity."
        copied = "Kerala has rivers, backwaters, forests, and coastal plains with rich biodiversity."
        assert _is_too_extractive(source, copied, [], []) is True

    @patch("app.modules.lesson_plan.generate_response")
    def test_rewrite_steps_abstractive_accepts_paraphrase(self, mock_generate):
        candidate_steps = [
            {
                "id": 1,
                "title": "Kerala Geography",
                "type": "concept",
                "status": "pending",
                "content": "Original",
                "_source": "Kerala includes hills, plains, and backwaters across districts.",
            }
        ]
        mock_generate.return_value = json.dumps(
            {
                "steps": [
                    {
                        "id": 1,
                        "title": "Kerala Geography",
                        "type": "concept",
                        "content": "This topic explains Kerala's varied landforms in simple terms.",
                        "bullets": [
                            "Different regions have different physical features",
                            "Water systems shape local life",
                        ],
                        "numbered": [],
                    }
                ]
            }
        )

        rewritten = _rewrite_steps_abstractive("Kerala", candidate_steps)
        assert len(rewritten) == 1
        assert rewritten[0]["content"]
        assert rewritten[0]["bullets"]


class TestListLessonSessions:
    @patch("app.modules.lesson_plan.get_connection")
    def test_list_lesson_sessions_returns_active_sessions(self, mock_conn):
        """Test that list_lesson_sessions returns saved sessions."""
        # Mock cursor
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            ("session1", "Chapter 1", json.dumps({}), "2026-03-29T10:00:00"),
            ("session2", "Chapter 2", json.dumps({}), "2026-03-29T11:00:00"),
        ]
        
        mock_conn.return_value.cursor.return_value = cursor
        
        sessions = list_lesson_sessions("user1")
        
        assert len(sessions) == 2
        assert sessions[0]["id"] == "session1"
        assert sessions[0]["chapter"] == "Chapter 1"

    @patch("app.modules.lesson_plan.get_connection")
    def test_list_lesson_sessions_with_custom_title(self, mock_conn):
        """Test that custom session titles are preserved."""
        cursor = MagicMock()
        plan_json = json.dumps({"session_title": "My Custom Title"})
        cursor.fetchall.return_value = [
            ("session1", "Chapter 1", plan_json, "2026-03-29T10:00:00"),
        ]
        
        mock_conn.return_value.cursor.return_value = cursor
        
        sessions = list_lesson_sessions("user1")
        
        assert sessions[0]["title"] == "My Custom Title"


class TestRenameLessonSession:
    @patch("app.modules.lesson_plan.get_connection")
    def test_rename_lesson_session_success(self, mock_conn):
        """Test successfully renaming a lesson session."""
        cursor = MagicMock()
        cursor.fetchall.return_value = [(1, json.dumps({}))]
        
        mock_conn.return_value.cursor.return_value = cursor
        
        result = rename_lesson_session("user1", "session1", "New Title")
        
        assert result["status"] == "updated"
        cursor.execute.assert_called()

    @patch("app.modules.lesson_plan.get_connection")
    def test_rename_lesson_session_not_found(self, mock_conn):
        """Test renaming non-existent session returns not_found."""
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        
        mock_conn.return_value.cursor.return_value = cursor
        
        result = rename_lesson_session("user1", "nonexistent", "New Title")
        
        assert result["status"] == "not_found"


class TestDeleteLessonSession:
    @patch("app.modules.lesson_plan.get_connection")
    def test_delete_lesson_session_success(self, mock_conn):
        """Test successfully deleting a lesson session and all related data."""
        cursor = MagicMock()
        cursor.fetchall.return_value = [(1,), (2,)]
        cursor.rowcount = 2
        
        mock_conn.return_value.cursor.return_value = cursor
        
        result = delete_lesson_session("user1", "session1")
        
        assert result["status"] == "deleted"
        assert result["deleted_plans"] == 2

    @patch("app.modules.lesson_plan.get_connection")
    def test_delete_lesson_session_empty(self, mock_conn):
        """Test deleting session with no plans."""
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        cursor.rowcount = 0
        
        mock_conn.return_value.cursor.return_value = cursor
        
        result = delete_lesson_session("user1", "session1")
        
        assert result["status"] == "deleted"
        assert result["deleted_plans"] == 0


class TestGetLessonPlan:
    @patch("app.modules.lesson_plan.get_connection")
    def test_get_lesson_plan_success(self, mock_conn):
        """Test successfully retrieving a lesson plan."""
        cursor = MagicMock()
        plan_json = json.dumps({"session_id": "session1", "chapter": "Chapter 1", "steps": []})
        cursor.fetchone.return_value = (1, plan_json)
        
        mock_conn.return_value.cursor.return_value = cursor
        
        plan = get_lesson_plan("user1", "session1")
        
        assert plan is not None
        assert plan["lesson_plan_id"] == 1
        assert plan["chapter"] == "Chapter 1"

    @patch("app.modules.lesson_plan.get_connection")
    def test_get_lesson_plan_not_found(self, mock_conn):
        """Test getting non-existent lesson plan returns None."""
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        
        mock_conn.return_value.cursor.return_value = cursor
        
        plan = get_lesson_plan("user1", "nonexistent")
        
        assert plan is None


class TestGetLessonPlanCards:
    @patch("app.modules.lesson_plan.get_connection")
    def test_get_lesson_plan_cards_success(self, mock_conn):
        """Test retrieving lesson plan cards."""
        cursor = MagicMock()
        # First call checks if plan exists
        cursor.fetchone.return_value = (1,)
        # Second call gets cards
        cursor.fetchall.return_value = [
            (1, 1, "Card 1", "concept", json.dumps({"content": "Content 1", "bullets": ["Point 1"], "numbered": []}), "pending", None),
            (2, 2, "Card 2", "example", json.dumps({"content": "Content 2", "bullets": [], "numbered": ["Step 1"]}), "pending", None),
        ]
        
        mock_conn.return_value.cursor.return_value = cursor
        
        cards = get_lesson_plan_cards("user1", 1)
        
        assert len(cards) == 2
        assert cards[0]["title"] == "Card 1"
        assert cards[1]["card_type"] == "example"
        assert cards[0]["bullets"] == ["Point 1."]
        assert cards[1]["numbered"] == ["Step 1."]

    @patch("app.modules.lesson_plan.get_connection")
    def test_get_lesson_plan_cards_unauthorized(self, mock_conn):
        """Test that accessing other user's cards returns empty."""
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        
        mock_conn.return_value.cursor.return_value = cursor
        
        cards = get_lesson_plan_cards("user1", 999)
        
        assert cards == []


class TestCompleteLessonCard:
    @patch("app.modules.lesson_plan.get_connection")
    def test_complete_lesson_card_success(self, mock_conn):
        """Test completing a lesson card."""
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        
        mock_conn.return_value.cursor.return_value = cursor
        
        result = complete_lesson_card("user1", 1, 1, "completed")
        
        assert result["status"] == "updated"
        assert result["card_id"] == 1

    @patch("app.modules.lesson_plan.get_connection")
    def test_complete_lesson_card_plan_not_found(self, mock_conn):
        """Test completing card for non-existent plan."""
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        
        mock_conn.return_value.cursor.return_value = cursor
        
        result = complete_lesson_card("user1", 999, 1, "completed")
        
        assert result["status"] == "not_found"


class TestGetCardForUser:
    @patch("app.modules.lesson_plan.get_connection")
    def test_get_card_for_user_success(self, mock_conn):
        """Test getting card for a user."""
        cursor = MagicMock()
        cursor.fetchone.return_value = (
            1,  # lesson_plan_id
            "session1",  # session_id
            99,  # card_id
            "Step 1",  # title
            "concept",  # card_type
            json.dumps({"content": "Learning content", "bullets": ["Point 1"], "numbered": ["Step A"]})  # content_json
        )
        
        mock_conn.return_value.cursor.return_value = cursor
        
        card = get_card_for_user("user1", 99)
        
        assert card is not None
        assert card["card_id"] == 99
        assert card["content"] == "Learning content"
        assert card["bullets"] == ["Point 1."]
        assert card["numbered"] == ["Step A."]

    @patch("app.modules.lesson_plan.get_connection")
    def test_get_card_for_user_not_found(self, mock_conn):
        """Test getting non-existent card returns None."""
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        
        mock_conn.return_value.cursor.return_value = cursor
        
        card = get_card_for_user("user1", 999)
        
        assert card is None


class TestUpdateStepProgress:
    @patch("app.modules.lesson_plan.get_connection")
    def test_update_step_progress_success(self, mock_conn):
        """Test updating step progress."""
        cursor = MagicMock()
        
        mock_conn.return_value.cursor.return_value = cursor
        
        result = update_step_progress("user1", "session1", 1, "completed")
        
        assert result["status"] == "updated"
        cursor.execute.assert_called()


class TestGetNextStep:
    @patch("app.modules.lesson_plan.get_lesson_plan")
    @patch("app.modules.lesson_plan.get_connection")
    def test_get_next_step_pending_step(self, mock_conn, mock_get_plan):
        """Test getting next pending step."""
        mock_get_plan.return_value = {
            "steps": [
                {"id": 1, "title": "Intro"},
                {"id": 2, "title": "Concepts"},
            ]
        }
        
        cursor = MagicMock()
        cursor.fetchone.return_value = None  # No progress for step 1
        
        mock_conn.return_value.cursor.return_value = cursor
        
        next_step = get_next_step("user1", "session1")
        
        assert next_step is not None
        assert next_step["id"] == 1

    @patch("app.modules.lesson_plan.get_lesson_plan")
    def test_get_next_step_no_plan(self, mock_get_plan):
        """Test getting next step when no plan exists."""
        mock_get_plan.return_value = None
        
        next_step = get_next_step("user1", "session1")
        
        assert next_step is None


class TestResetLessonProgress:
    @patch("app.modules.lesson_plan.get_connection")
    def test_reset_lesson_progress_success(self, mock_conn):
        """Test resetting lesson progress."""
        cursor = MagicMock()
        
        mock_conn.return_value.cursor.return_value = cursor
        
        result = reset_lesson_progress("user1", "session1")
        
        assert result["status"] == "progress reset"
        cursor.execute.assert_called()
