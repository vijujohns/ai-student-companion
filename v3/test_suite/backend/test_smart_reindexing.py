from unittest.mock import mock_open, patch

import numpy as np

from app import main
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

    def test_load_index_keeps_imported_document_aliases_in_sync(self):
        original_docs = list(faiss_store.documents)
        original_kb_docs = list(kb_sync.documents)
        original_indexes = dict(getattr(faiss_store, "logical_indexes", {}))
        loaded_documents = [{"text": "already indexed", "source": "chapter1.pdf", "metadata": {}, "index_name": "general_index"}]

        try:
            faiss_store.documents[:] = []
            kb_sync.documents[:] = []
            faiss_store.logical_indexes.clear()

            with (
                patch("app.modules.faiss_store.os.path.exists", side_effect=lambda path: True),
                patch("app.modules.faiss_store.faiss.read_index"),
                patch("builtins.open", mock_open(read_data=b"data")),
                patch("app.modules.faiss_store.pickle.load", return_value=loaded_documents),
                patch("app.modules.faiss_store.json.load", return_value={"general_index": [0]}),
            ):
                faiss_store.load_index()

            assert faiss_store.documents == loaded_documents
            assert kb_sync.documents == loaded_documents
        finally:
            faiss_store.documents[:] = original_docs
            kb_sync.documents[:] = original_kb_docs
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

        assert result["status"] == "completed"
        assert result["reindexed_files"] == 1
        assert result["total_files"] == 1
        assert result["mode"] in {"full", "file"}
        assert result["processed_files"] == ["chapter1.pdf"]
        assert "qa_index" in result["index_targets"]

        progress = kb_sync.get_reindex_progress()
        assert progress["status"] == "completed"
        assert progress["processed_files"] == ["chapter1.pdf"]
        assert progress["progress_percent"] == 100
        mock_ingest.assert_called_once_with(str(pdf_path), use_llm_summary=False)

    def test_incremental_reindex_skips_unchanged_files(self, tmp_path):
        kb_root = tmp_path / "knowledge_base"
        kb_root.mkdir()
        pdf_path = kb_root / "chapter1.pdf"
        pdf_path.write_text("placeholder", encoding="utf-8")
        last_modified = pdf_path.stat().st_mtime

        with (
            patch("app.modules.kb_sync.BASE_DIR", str(tmp_path)),
            patch("app.modules.kb_sync.load_metadata", return_value={str(pdf_path): last_modified}),
            patch("app.modules.kb_sync.faiss_store.documents", [{"text": "already indexed"}]),
            patch("app.modules.kb_sync.save_metadata"),
            patch("app.modules.kb_sync.save_index"),
            patch("app.modules.kb_sync._remove_docs_for_source"),
            patch("app.modules.kb_sync._reset_store"),
            patch("app.modules.kb_sync.ingest_pdf") as mock_ingest,
        ):
            result = kb_sync.load_knowledge_base(force_reindex=False)

        assert result["status"] == "completed"
        assert result["mode"] == "incremental"
        assert result["reindexed_files"] == 0
        assert result["skipped_files"] == 1
        assert result["skipped_paths"] == ["chapter1.pdf"]
        mock_ingest.assert_not_called()

    def test_background_reindex_uses_fast_summary_mode(self, tmp_path):
        kb_root = tmp_path / "knowledge_base"
        kb_root.mkdir()
        pdf_path = kb_root / "chapter1.pdf"
        pdf_path.write_text("placeholder", encoding="utf-8")

        with (
            patch("app.modules.kb_sync.BASE_DIR", str(tmp_path)),
            patch("app.modules.kb_sync.load_metadata", return_value={}),
            patch("app.modules.kb_sync.save_metadata"),
            patch("app.modules.kb_sync.save_index"),
            patch("app.modules.kb_sync._remove_docs_for_source"),
            patch("app.modules.kb_sync.ingest_pdf") as mock_ingest,
        ):
            result = kb_sync.load_knowledge_base(force_reindex=False)

        assert result["status"] == "completed"
        mock_ingest.assert_called_once_with(str(pdf_path), use_llm_summary=False)


class TestStartupReindexMode:
    def test_resolve_startup_reindex_mode_defaults_to_skip(self):
        with patch.dict("os.environ", {}, clear=True):
            assert main._resolve_startup_reindex_mode() == "skip"

    def test_resolve_startup_reindex_mode_supports_flag_values(self):
        with patch.dict("os.environ", {"KB_REINDEX_MODE": "true"}, clear=True):
            assert main._resolve_startup_reindex_mode() == "incremental"

        with patch.dict("os.environ", {"KB_REINDEX_MODE": "full"}, clear=True):
            assert main._resolve_startup_reindex_mode() == "full"

        with patch.dict("os.environ", {"SKIP_KB_REINDEX": "1"}, clear=True):
            assert main._resolve_startup_reindex_mode() == "skip"
