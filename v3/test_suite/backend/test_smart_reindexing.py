from unittest.mock import patch

import numpy as np

from app.modules import faiss_store, ingestion, kb_sync


class TestSmartChunkMetadata:
    def test_build_chunk_metadata_classifies_formula_content(self):
        metadata = ingestion.build_chunk_metadata(
            "Formula: Area of triangle = 1/2 x base x height.",
            source_path=r"D:\GPT\ai-student-companion\v3\knowledge_base\Class X\Math\areas.pdf",
        )

        assert metadata["type"] == "formula"
        assert metadata["index_name"] == "formula_index"
        assert metadata["chapter"]
        assert metadata["topic"]


class TestLogicalMultiIndexStore:
    def test_add_doc_persists_index_name_metadata(self):
        original_docs = list(faiss_store.documents)
        original_indexes = dict(getattr(faiss_store, "logical_indexes", {}))
        try:
            faiss_store.documents[:] = []
            if hasattr(faiss_store, "logical_indexes"):
                faiss_store.logical_indexes.clear()

            with (
                patch.object(faiss_store.model, "encode", return_value=np.array([[0.1, 0.2]], dtype="float32")),
                patch.object(faiss_store.index, "add", return_value=None),
            ):
                faiss_store.add_doc(
                    "Formula: F = m * a",
                    source="physics.pdf",
                    metadata={
                        "index_name": "formula_index",
                        "type": "formula",
                        "chapter": "Force",
                        "topic": "Newton's second law",
                    },
                )

            stored = faiss_store.documents[0]
            assert stored["index_name"] == "formula_index"
            assert stored["metadata"]["type"] == "formula"
        finally:
            faiss_store.documents[:] = original_docs
            if hasattr(faiss_store, "logical_indexes"):
                faiss_store.logical_indexes.clear()
                faiss_store.logical_indexes.update(original_indexes)


class TestSmartReindexSummary:
    def test_load_knowledge_base_returns_progress_summary(self, tmp_path):
        pdf_path = tmp_path / "chapter1.pdf"
        pdf_path.write_text("placeholder", encoding="utf-8")

        with (
            patch("app.modules.kb_sync.BASE_DIR", str(tmp_path)),
            patch("app.modules.kb_sync.load_metadata", return_value={}),
            patch("app.modules.kb_sync.save_metadata"),
            patch("app.modules.kb_sync.save_index"),
            patch("app.modules.kb_sync._remove_docs_for_source"),
            patch("app.modules.kb_sync._reset_store"),
            patch("app.modules.kb_sync.ingest_pdf") as mock_ingest,
        ):
            result = kb_sync.load_knowledge_base(force_reindex=True, target_path=str(pdf_path))

        assert result["reindexed_files"] == 1
        assert result["mode"] in {"full", "selective"}
        mock_ingest.assert_called_once_with(str(pdf_path))
