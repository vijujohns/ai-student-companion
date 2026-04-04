from unittest.mock import patch

from app.api import routes
from app.schemas.request import AskRequest
from app.modules.task_router import TaskRoute

from app.modules.flashcards import FlashcardItem
from app.modules.generator_executor import execute_generator_task


class TestGeneratorExecutor:
    def test_summary_task_prefers_saved_pdf_summary(self):
        with (
            patch("app.modules.generator_executor.resolve_content_reference", return_value={"path": "doc.pdf", "title": "Plants Notes"}),
            patch("app.modules.generator_executor.get_summary", return_value="Plants make food using sunlight."),
            patch("app.modules.generator_executor.search", return_value=[]),
            patch("app.modules.generator_executor.generate_response") as mock_generate,
        ):
            result = execute_generator_task(
                task="summary",
                query="Summarize this chapter",
                user_id="student",
                session_id="s1",
                content_id="upload:7",
            )

        assert "Plants make food using sunlight." in result
        mock_generate.assert_not_called()

    def test_flashcards_task_formats_cards(self):
        with (
            patch("app.modules.generator_executor.search", return_value=["Cells are basic units of life."]),
            patch(
                "app.modules.generator_executor.generate_flashcards_from_text",
                return_value=[FlashcardItem(question="What is a cell?", answer="The basic unit of life.")],
            ),
        ):
            result = execute_generator_task(
                task="flashcards",
                query="Make flashcards on cells",
                user_id="student",
                session_id="s1",
            )

        assert "Flashcards" in result
        assert "What is a cell?" in result


class TestAskGeneratorIntegration:
    def test_ask_endpoint_routes_quiz_task_to_generator_executor(self):
        fake_route = TaskRoute(
            task="quiz",
            model_task="quiz",
            retrieval_scope="curriculum",
            confidence=0.95,
            reason="keyword:quiz",
            source="/ask",
            explicit=True,
        )

        with (
            patch("app.api.routes._consume_quota_or_raise", return_value=None),
            patch("app.api.routes.route_task", return_value=fake_route),
            patch("app.api.routes.execute_generator_task", return_value="Quiz generator output", create=True) as mock_exec,
            patch("app.api.routes.generate_answer", return_value="fallback answer") as mock_answer,
        ):
            body = routes.ask(AskRequest(query="Create a quiz on motion", task="quiz"), user={"username": "student"})

        assert body["answer"] == "Quiz generator output"
        mock_exec.assert_called_once()
        mock_answer.assert_not_called()
