from unittest.mock import patch

from app.api import routes
from app.modules.task_router import TaskRoute
from app.schemas.request import AskRequest
from app.modules.math_executor import execute_math_task
from app.modules.translation_executor import execute_translation_task


class TestMathExecutor:
    def test_execute_math_task_solves_linear_equation(self):
        result = execute_math_task(
            query="solve x + 2 = 5",
            user_id="student",
            session_id="s1",
        )

        assert "x = 3" in result

    def test_execute_math_task_evaluates_expression(self):
        result = execute_math_task(
            query="2 + 3 * 4",
            user_id="student",
            session_id="s1",
        )

        assert "14" in result


class TestTranslationExecutor:
    @patch("app.modules.translation_executor.translate_text", return_value="नमस्ते")
    def test_execute_translation_task_extracts_target_and_text(self, mock_translate):
        result = execute_translation_task(
            query="Translate hello to Hindi",
            user_id="student",
            session_id="s1",
        )

        assert "नमस्ते" in result
        mock_translate.assert_called_once_with("hello", target="hi", source="auto")


class TestAskUtilityIntegration:
    def test_ask_endpoint_routes_math_task_to_utility_executor(self):
        fake_route = TaskRoute(
            task="math",
            model_task="math",
            retrieval_scope="curriculum",
            confidence=0.92,
            reason="pattern:math",
            source="/ask",
            explicit=True,
        )

        with (
            patch("app.api.routes._consume_quota_or_raise", return_value=None),
            patch("app.api.routes.route_task", return_value=fake_route),
            patch("app.api.routes.execute_utility_task", return_value="Math utility output", create=True) as mock_exec,
            patch("app.api.routes.generate_answer", return_value="fallback answer") as mock_answer,
        ):
            body = routes.ask(AskRequest(query="solve x + 2 = 5", task="math"), user={"username": "student"})

        assert body["answer"] == "Math utility output"
        mock_exec.assert_called_once()
        mock_answer.assert_not_called()
