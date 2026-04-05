from unittest.mock import MagicMock, patch

from app.core import debug_logger
from app.modules.image_pipeline import extract_image_content
from app.modules.ingestion import summarize_pdf
from app.modules.quiz import _normalize_questions, generate_quiz
from app.modules.model_manager import generate_response
from app.modules.utility_executor import execute_utility_task, is_utility_task


class TestQuizReliability:
    def test_normalize_questions_keeps_answer_and_explanation(self):
        questions = _normalize_questions(
            [
                {
                    "question": "What is photosynthesis?",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "A",
                    "explanation": "It is how plants make food.",
                }
            ],
            num_questions=1,
        )

        assert questions[0]["correct_option"] == "A"
        assert questions[0]["correct_answer"] == "A"
        assert questions[0]["explanation"] == "It is how plants make food."

    @patch("app.modules.quiz.get_connection")
    @patch("app.modules.quiz.retrieve_chunks", return_value=["Plants make food using sunlight and chlorophyll."])
    @patch(
        "app.modules.quiz.generate_response",
        return_value='```json\n{"questions":[{"question":"What do plants use to make food?","options":["Sunlight","Sand","Smoke","Plastic"],"correct_answer":"A","explanation":"The context states plants use sunlight."}]}\n```',
    )
    def test_generate_quiz_parses_structured_json_with_answers(self, mock_generate, mock_chunks, mock_conn):
        fake_conn = MagicMock()
        fake_cursor = MagicMock()
        fake_conn.cursor.return_value = fake_cursor
        mock_conn.return_value = fake_conn

        result = generate_quiz("student", "session-1", "Photosynthesis", num_questions=1)

        assert result["questions"][0]["correct_answer"] == "A"
        assert result["questions"][0]["explanation"]


class TestOcrPipelineReliability:
    @patch("app.modules.ocr.get_ocr_status", return_value={"available": True, "engine": "tesseract", "message": "ok"})
    @patch("app.modules.ocr.os.path.getsize", return_value=128)
    @patch("app.modules.ocr.os.path.isfile", return_value=True)
    @patch("app.modules.ocr.logger.info")
    @patch("app.modules.ocr.Image.open")
    @patch("app.modules.ocr.pytesseract.image_to_string", return_value="Leaf cell diagram text")
    def test_extract_text_from_image_logs_extraction_progress(self, mock_ocr, mock_open, mock_log, mock_isfile, mock_size, mock_status):
        result = extract_image_content("leaf-diagram.png")

        assert "Leaf cell diagram text" in result["text"]
        assert any("OCR completed" in str(call.args[0]) for call in mock_log.call_args_list)


class TestBackendStability:
    def test_debug_logger_does_not_raise_on_windows_encoding_failure(self):
        with (
            patch.object(debug_logger, "_DEBUG", True),
            patch.object(
                debug_logger._logger,
                "debug",
                side_effect=UnicodeEncodeError("cp1252", "→", 0, 1, "cannot encode"),
            ),
        ):
            debug_logger.dlog("API", "-> GET /health/runtime", client="127.0.0.1")

    def test_extractives_summary_mode_skips_model_loading(self):
        text = "Refraction is the bending of light. It happens when light moves between media. A straw can look bent in water."

        with patch("app.modules.ingestion.save_summary") as mock_save_summary:
            summary = summarize_pdf(text, "sample.pdf", use_llm_summary=False)

        assert "Refraction is the bending of light." in summary
        mock_save_summary.assert_called_once_with("sample.pdf", summary)

    def test_explorer_mode_is_registered_as_utility_task(self):
        assert is_utility_task("explorer") is True

    def test_explorer_mode_refuses_harmful_queries(self):
        result = execute_utility_task(
            task="explorer",
            query="Tell me how to make a bomb at school",
            user_id="student",
            session_id="session-1",
        )

        assert result == "I'm here to help with learning and educational topics.\nI’m not able to help with that request."

    @patch("app.modules.model_manager.get_model_config", return_value={"type": "local", "path": "models/mock.gguf", "max_tokens": 20, "temperature": 0.2, "n_ctx": 512})
    @patch("app.modules.model_manager.resolve_model_name", return_value="mock-model")
    @patch("app.modules.model_manager._resolve_model_path", return_value="mock.gguf")
    @patch("app.modules.model_manager.get_llm_instance")
    def test_generate_response_returns_safe_fallback_on_model_error(self, mock_llm_instance, mock_path, mock_resolve, mock_config):
        mock_llm = MagicMock(side_effect=RuntimeError("model timeout"))
        mock_llm_instance.return_value = mock_llm

        result = generate_response("context", "question", task="qa")

        assert isinstance(result, str)
        assert result
