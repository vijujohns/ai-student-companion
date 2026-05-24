import numpy as np
from unittest.mock import MagicMock, patch

from app.modules import faiss_store, rag


class TestHybridRetrieval:
    def test_faiss_search_supports_hybrid_multi_index_details(self):
        original_docs = list(faiss_store.documents)
        try:
            faiss_store.documents[:] = [
                {"text": "General unrelated note.", "source": r"D:\GPT\ai-student-companion\v3\knowledge_base\General\misc.pdf"},
                {"text": "Photosynthesis uses chlorophyll and sunlight to make food.", "source": r"D:\GPT\ai-student-companion\v3\knowledge_base\Class X\Science\bio.pdf"},
                {"text": "My uploaded photosynthesis summary with chlorophyll examples.", "source": r"D:\GPT\ai-student-companion\v3\uploads\abc123\notes.pdf"},
            ]

            with (
                patch.object(faiss_store.model, "encode", return_value=np.array([[0.1, 0.2]], dtype="float32")),
                patch.object(
                    faiss_store.index,
                    "search",
                    return_value=(
                        np.array([[0.01, 0.20, 0.25]], dtype="float32"),
                        np.array([[0, 1, 2]], dtype="int64"),
                    ),
                ),
            ):
                results = faiss_store.search(
                    "photosynthesis chlorophyll",
                    top_k=2,
                    search_k=3,
                    task="quiz",
                    return_details=True,
                )

            assert len(results) == 2
            assert results[0]["source_type"] in {"curriculum", "upload"}
            assert "photosynthesis" in results[0]["text"].lower()
            assert all("score" in item for item in results)
        finally:
            faiss_store.documents[:] = original_docs

    def test_generate_answer_passes_task_to_search(self):
        fake_conn = MagicMock()
        fake_cursor = MagicMock()
        fake_cursor.fetchone.return_value = None
        fake_conn.cursor.return_value = fake_cursor

        with (
            patch("app.modules.rag.get_connection", return_value=fake_conn),
            patch("app.modules.rag.get_cache", return_value=None),
            patch("app.modules.rag.search", return_value=["Plants grow using sunlight in the retrieved chunk"]) as mock_search,
            patch("app.modules.rag.generate_response", return_value="Plants grow using sunlight in the retrieved chunk"),
            patch("app.modules.rag.set_cache"),
            patch("app.modules.rag.save_chat"),
        ):
            result = rag.generate_answer("Create a quiz on plants", "user1", "session1", task="quiz")

        assert result == "Plants grow using sunlight in the retrieved chunk"
        assert mock_search.call_args.kwargs["task"] == "quiz"
