from unittest.mock import patch

from app.modules import ingestion
from app.modules.image_pipeline import extract_image_content


class TestImagePipeline:
    def test_extract_image_content_builds_summary_from_ocr_text(self):
        with (
            patch("app.modules.image_pipeline.extract_text_from_image", return_value="Plants need sunlight and water for food making."),
            patch("app.modules.image_pipeline.generate_response", return_value="This image explains how plants make food using sunlight.") as mock_generate,
        ):
            result = extract_image_content(r"D:\images\leaf-diagram.png", model_name="m1")

        assert result["title"] == "leaf diagram"
        assert "sunlight and water" in result["text"].lower()
        assert result["summary"] == "This image explains how plants make food using sunlight."
        assert "plants" in result["keywords"]
        mock_generate.assert_called_once()

    def test_extract_image_content_uses_filename_hints_when_ocr_is_blank(self):
        with (
            patch("app.modules.image_pipeline.extract_text_from_image", return_value=""),
            patch("app.modules.image_pipeline.generate_response") as mock_generate,
        ):
            result = extract_image_content(r"D:\images\triangle-area-diagram.png")

        assert "triangle area diagram" in result["text"].lower()
        assert result["summary"]
        mock_generate.assert_not_called()


class TestIngestImage:
    @patch("app.modules.ingestion.chunk_text", return_value=["Leaf cells contain chlorophyll."])
    @patch("app.modules.ingestion.save_summary")
    @patch(
        "app.modules.image_pipeline.extract_image_content",
        return_value={
            "title": "leaf diagram",
            "text": "Leaf cells contain chlorophyll.",
            "summary": "The image highlights chlorophyll inside leaf cells.",
            "keywords": ["leaf", "chlorophyll"],
            "modality": "image",
        },
    )
    @patch("app.modules.faiss_store.add_doc")
    def test_ingest_image_saves_summary_and_enriches_chunks(self, mock_add_doc, mock_extract, mock_save_summary, mock_chunk_text):
        ingestion.ingest_image("leaf-diagram.png")

        mock_extract.assert_called_once_with("leaf-diagram.png", model_name=None)
        mock_save_summary.assert_called_once_with("leaf-diagram.png", "The image highlights chlorophyll inside leaf cells.")
        added_chunk = mock_add_doc.call_args.args[0]
        assert "Image: leaf diagram" in added_chunk
        assert "OCR Summary:" in added_chunk
