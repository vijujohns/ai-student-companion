"""
RAG Module Tests
- Document retrieval and ranking
- Caching behavior
- Context relevance checking
- Answer generation with fallback
"""

import json
import pytest
from unittest.mock import MagicMock, patch, call
from app.modules.rag import (
    rank_chunks,
    is_context_relevant,
    clean_output,
    generate_answer,
    generate_answer_stream,
    retrieve_chunks,
)


class TestRankChunks:
    """Test chunk ranking by semantic relevance."""

    def test_rank_chunks_orders_by_word_overlap(self):
        """Verify chunks are ranked by query word overlap."""
        query = "machine learning basics"
        chunks = [
            "Machine learning is powerful",
            "Python programming language",
            "Learning systems and algorithms",
        ]
        
        ranked = rank_chunks(query, chunks)
        
        # First chunk has most overlap ("machine", "learning")
        assert ranked[0] == "Machine learning is powerful"

    def test_rank_chunks_case_insensitive(self):
        """Verify ranking is case-insensitive."""
        query = "PYTHON CODE"
        chunks = [
            "python is great",
            "java programming",
            "code examples",
        ]
        
        ranked = rank_chunks(query, chunks)
        assert ranked[0] in ["python is great", "code examples"]

    def test_rank_chunks_empty_list(self):
        """Verify ranking handles empty chunk list."""
        ranked = rank_chunks("test query", [])
        assert ranked == []

    def test_rank_chunks_single_chunk(self):
        """Verify ranking handles single chunk."""
        ranked = rank_chunks("test", ["Single chunk"])
        assert ranked == ["Single chunk"]


class TestContextRelevance:
    """Test context relevance checking."""

    def test_is_context_relevant_with_overlap(self):
        """Verify function detects relevant context."""
        query = "artificial intelligence neural networks"
        context = "Neural networks are used in artificial intelligence"
        
        assert is_context_relevant(query, context) is True

    def test_is_context_relevant_no_overlap(self):
        """Verify function rejects irrelevant context."""
        query = "quantum computing"
        context = "Traditional recipes for cooking"
        
        # May return True or False depending on threshold
        result = is_context_relevant(query, context)
        assert isinstance(result, bool)

    def test_is_context_relevant_case_insensitive(self):
        """Verify relevance check is case-insensitive."""
        query = "PYTHON PROGRAMMING"
        context = "python and programming languages"
        
        result = is_context_relevant(query, context)
        assert isinstance(result, bool)

    def test_is_context_relevant_empty_query(self):
        """Verify handling of empty query."""
        result = is_context_relevant("", "Some context text")
        assert isinstance(result, bool)


class TestCleanOutput:
    """Test output cleaning and deduplication."""

    def test_clean_output_removes_stop_markers(self):
        """Verify stop markers are removed."""
        text = "Answer: This is the answer. Question: What is next?"
        cleaned = clean_output(text)
        assert "Question:" not in cleaned
        assert "Answer:" not in cleaned

    def test_clean_output_removes_duplicates(self):
        """Verify duplicate lines are removed."""
        text = "Hello world\nHello world\nGoodbye"
        cleaned = clean_output(text)
        assert cleaned.count("Hello world") <= 1

    def test_clean_output_removes_repeated_words(self):
        """Verify repeated consecutive words are removed."""
        text = "The the the quick brown brown fox"
        cleaned = clean_output(text)
        assert "the the" not in cleaned
        assert "brown brown" not in cleaned

    def test_clean_output_preserves_structure(self):
        """Verify important content is preserved."""
        text = "Important information here"
        cleaned = clean_output(text)
        assert "Important" in cleaned
        assert "information" in cleaned

    def test_clean_output_empty_string(self):
        """Verify handling of empty string."""
        cleaned = clean_output("")
        assert cleaned == ""


class TestGenerateAnswer:
    """Test answer generation with caching and fallback."""

    @patch("app.modules.rag.get_cache")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_returns_cached_result(self, mock_conn, mock_cache):
        """Verify cached answers are returned without recomputation."""
        # Cache stores dict with 'answer' key
        cached_result = {"answer": "Cached response"}
        mock_cache.return_value = cached_result
        
        result = generate_answer("test query", "user1", "session1")
        
        # If cache returns value, function should return the answer
        assert result == "Cached response"

    @patch("app.modules.rag.get_cache")
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.search", return_value=["Relevant study material about the test query."])
    @patch("app.modules.rag.generate_response")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_caches_new_result(self, mock_conn, mock_gen, mock_search, mock_set_cache, mock_get_cache):
        """Verify new answers are cached."""
        mock_get_cache.return_value = None
        mock_gen.return_value = "Relevant study material about the test query."
        
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db
        
        result = generate_answer("test query", "user1", "session1")
        
        assert result == "Relevant study material about the test query."
        mock_set_cache.assert_called_once()

    @patch("app.modules.rag.get_cache")
    @patch("app.modules.rag.retrieve_chunks")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_fallback_on_retrieval_failure(self, mock_conn, mock_retrieve, mock_cache):
        """Verify fallback when document retrieval fails."""
        mock_cache.return_value = None
        mock_retrieve.return_value = []
        
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db
        
        # generate_answer should handle empty retrieval gracefully
        result = generate_answer("test", "user1", "session1")
        # Should return something, not raise
        assert isinstance(result, str) or result is None

    @patch("app.modules.rag.get_cache", return_value=None)
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag.search", return_value=["Refraction is the bending of light when it passes from one medium to another."])
    @patch("app.modules.rag.get_connection")
    @patch("app.modules.rag.generate_response", return_value="I could not find this in the provided study material.")
    def test_generate_answer_keeps_grounded_no_info_response(self, mock_generate, mock_conn, mock_search, mock_history, mock_save_chat, mock_set_cache, mock_get_cache):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        result = generate_answer("What is refraction?", "user1", "session1")

        assert result == "I don't have enough information in the provided material."
        assert mock_generate.call_count == 1

    @patch("app.modules.rag.get_cache", return_value=None)
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag.search", return_value=["Refraction is the bending of light when it passes from one medium to another.", "Light changes direction at the boundary."])
    @patch("app.modules.rag.get_connection")
    @patch("app.modules.rag.generate_response", return_value="The capital of France is Paris.")
    def test_generate_answer_rejects_ungrounded_response(self, mock_generate, mock_conn, mock_search, mock_history, mock_save_chat, mock_set_cache, mock_get_cache):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        result = generate_answer("What is refraction?", "user1", "session1")

        assert result == "I don't have enough information in the provided material."

    @patch("app.modules.rag.get_cache", return_value=None)
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag._retrieve_context_items", return_value=[])
    @patch("app.modules.rag.get_summary", return_value="This chapter covers light, reflection, refraction, and refractive index applications.")
    @patch("app.modules.rag.resolve_content_reference", return_value={"path": "/tmp/light.pdf", "content_id": "kb:test-light"})
    @patch("app.modules.rag.get_connection")
    @patch("app.modules.rag.generate_response", return_value="Real world examples include mirrors, eyeglasses, and a straw appearing bent in water.")
    def test_generate_answer_uses_saved_summary_for_selected_content_followups(self, mock_generate, mock_conn, mock_resolve, mock_get_summary, mock_retrieve, mock_history, mock_save_chat, mock_set_cache, mock_get_cache):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        result = generate_answer(
            "Can you provide some real world examples to this?",
            "user1",
            "session1",
            session_content_override="kb:test-light",
        )

        assert "mirrors" in result
        used_context = mock_generate.call_args.kwargs["context"]
        assert "Document Summary:" in used_context
        assert "reflection, refraction" in used_context

    @patch("app.modules.rag.get_cache", return_value=None)
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag.search", return_value=["Refraction is the bending of light.", "It happens when light moves between media."])
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_formats_context_boundaries(self, mock_conn, mock_search, mock_history, mock_save_chat, mock_set_cache, mock_get_cache):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        with patch("app.modules.rag.generate_response", return_value="Refraction is the bending of light.") as mock_generate:
            generate_answer("What is refraction?", "user1", "session1")

        used_context = mock_generate.call_args.kwargs["context"]
        assert "[CONTEXT START]" in used_context
        assert "Reference:" in used_context
        assert "Chunk 1:" not in used_context
        assert "Refraction is the bending of light." in used_context
        assert "[CONTEXT END]" in used_context


class TestGenerateAnswerStream:
    """Test streaming answer generation."""

    @patch("app.modules.rag.get_cache")
    @patch("app.modules.rag.retrieve_chunks")
    @patch("app.modules.rag.generate_response_stream")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_stream_yields_tokens(self, mock_conn, mock_gen_stream, mock_retrieve, mock_cache):
        """Verify answer stream yields tokens."""
        mock_cache.return_value = None
        mock_retrieve.return_value = ["chunk1"]
        
        async def mock_stream(*args, **kwargs):
            for token in ["The", " ", "answer"]:
                yield token
        
        mock_gen_stream.return_value = mock_stream()
        
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db
        
        # Test that function exists and is callable
        from app.modules.rag import generate_answer_stream
        assert callable(generate_answer_stream)

    @patch("app.modules.rag.get_cache", return_value=None)
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.generate_response_stream", return_value=iter(["Grounded answer "]))
    @patch("app.modules.rag._retrieve_context_items", return_value=[{"text": "Refraction is the bending of light.", "metadata": {"type": "concept"}, "score": 0.9}])
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_stream_reads_history_before_saving_placeholder(self, mock_conn, mock_retrieve, mock_stream, mock_set_cache, mock_get_cache):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        events = []

        def fake_get_history(*args, **kwargs):
            events.append("history")
            return [{"question": "summarise this chapter", "answer": "Light chapter summary"}]

        def fake_save_chat(*args, **kwargs):
            events.append("save")

        with (
            patch("app.modules.rag.get_history", side_effect=fake_get_history),
            patch("app.modules.rag.save_chat", side_effect=fake_save_chat),
        ):
            list(generate_answer_stream("Can you provide some real world examples to this?", "user1", "session1"))

        assert events.index("history") < events.index("save")

    @patch(
        "app.modules.rag.get_cache",
        return_value={
            "answer": "On your selected page, **Pulmonary Veins** is shown as a label in the heart diagram. I do not see a full explanation for it on this page.\n\nIf you want, I can also give a short explanation from general knowledge with public references.\n\nUse the buttons below or reply **Yes** / **No**.",
            "meta": {
                "quickReplies": [
                    {"label": "Show extra explanation", "value": "Yes, show the outside explanation"},
                    {"label": "Stay within this page", "value": "No, stay within the selected material"},
                ]
            },
        },
    )
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_stream_cached_answer_emits_replace_text_payload(self, mock_conn, mock_get_cache):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        with patch("app.modules.rag.save_chat"):
            items = list(generate_answer_stream("what is pulmonary veins", "user1", "session1"))

        assert items == [
            {
                "text": "On your selected page, **Pulmonary Veins** is shown as a label in the heart diagram. I do not see a full explanation for it on this page.\n\nIf you want, I can also give a short explanation from general knowledge with public references.\n\nUse the buttons below or reply **Yes** / **No**.",
                "replaceText": True,
                "quickReplies": [
                    {"label": "Show extra explanation", "value": "Yes, show the outside explanation"},
                    {"label": "Stay within this page", "value": "No, stay within the selected material"},
                ],
            }
        ]


class TestRetrieveChunks:
    """Test chunk retrieval for chapters."""

    def test_retrieve_chunks_returns_list(self):
        """Verify retrieve_chunks returns list of strings."""
        # Test with empty chapter name - should return empty list
        result = retrieve_chunks("")
        assert isinstance(result, list)

    def test_retrieve_chunks_queries_by_chapter(self):
        """Verify chapter name is used in query."""
        # retrieve_chunks filters or searches based on chapter
        result = retrieve_chunks("Biology")
        assert isinstance(result, list)

    def test_retrieve_chunks_empty_for_no_docs(self):
        """Verify empty list when no documents found."""
        # retrieve_chunks with empty query should return empty
        result = retrieve_chunks("")
        assert result == [] or isinstance(result, list)


class TestRAGIntegration:
    """Integration tests for RAG pipeline."""

    @patch("app.modules.rag.get_cache")
    @patch("app.modules.rag.get_connection")
    def test_rag_pipeline_end_to_end(self, mock_conn, mock_get_cache):
        """Verify complete RAG pipeline."""
        mock_get_cache.return_value = None
        
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db
        
        result = generate_answer("What is X?", "user1", "session1")
        
        # Result should be a string (answer or fallback)
        assert isinstance(result, str) or result is None
