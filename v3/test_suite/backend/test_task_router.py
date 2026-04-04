from unittest.mock import patch

from app.api import routes
from app.schemas.request import AskRequest

from app.modules.task_router import TaskRoute, route_task


class TestTaskRouter:
    def test_route_task_prefers_explicit_task(self):
        routed = route_task("Help me revise this", route="/ask", requested_task="flashcard")

        assert routed.task == "flashcards"
        assert routed.model_task == "flashcards"
        assert routed.explicit is True

    def test_route_task_detects_summary_requests(self):
        routed = route_task("Please summarize this chapter in short points", route="/ask", content_id="upload:7")

        assert routed.task == "summary"
        assert routed.model_task == "summary"
        assert routed.reason.startswith("summary")

    def test_route_task_detects_quiz_keywords(self):
        routed = route_task("Create a quick MCQ quiz on photosynthesis", route="/ask")

        assert routed.task == "quiz"
        assert routed.model_task == "quiz"
        assert routed.confidence >= 0.7


class TestAskRouteIntegration:
    def test_ask_endpoint_routes_before_generation(self):
        fake_route = TaskRoute(
            task="quiz",
            model_task="quiz",
            retrieval_scope="curriculum",
            confidence=0.92,
            reason="keyword:quiz",
            source="/ask",
            explicit=False,
        )

        with (
            patch("app.api.routes._consume_quota_or_raise", return_value=None),
            patch("app.api.routes.route_task", return_value=fake_route) as mock_route,
            patch("app.api.routes.generate_answer", return_value="Answer here.") as mock_generate,
        ):
            body = routes.ask(AskRequest(query="Create a quiz on forces"), user={"username": "student"})

        assert body["answer"] == "Answer here."
        mock_route.assert_called_once()
        assert mock_generate.call_args.kwargs["task"] == "quiz"
