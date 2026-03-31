"""Targeted behavior tests for websocket API routes."""

import asyncio
import json
from unittest.mock import patch

from fastapi import WebSocketDisconnect

from app.api import websocket as ws_mod


class FakeWebSocket:
    def __init__(self, incoming=None):
        self.incoming = list(incoming or [])
        self.headers = {}
        self.query_params = {}
        self.accepted = False
        self.accept_subprotocol = None
        self.closed = None
        self.sent_texts = []
        self.client = None

    async def accept(self, subprotocol=None):
        self.accepted = True
        self.accept_subprotocol = subprotocol

    async def close(self, code=None, reason=None):
        self.closed = {"code": code, "reason": reason}

    async def receive_text(self):
        if not self.incoming:
            raise WebSocketDisconnect(code=1000)
        value = self.incoming.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    async def send_text(self, text):
        self.sent_texts.append(text)


def _run(coro):
    return asyncio.run(coro)


class TestSendJson:
    def test_send_json_writes_json(self):
        ws = FakeWebSocket()
        _run(ws_mod.send_json(ws, {"type": "chunk", "data": "x"}))
        assert ws.sent_texts == ['{"type": "chunk", "data": "x"}']

    def test_send_json_swallow_send_errors(self):
        class BrokenWs(FakeWebSocket):
            async def send_text(self, text):
                raise RuntimeError("boom")

        ws = BrokenWs()
        _run(ws_mod.send_json(ws, {"type": "error", "data": "x"}))


class TestBasicWsEndpoint:
    @patch("app.api.websocket.authenticate_websocket")
    def test_websocket_endpoint_rejects_unauthorized(self, mock_auth):
        mock_auth.return_value = None
        ws = FakeWebSocket()

        _run(ws_mod.websocket_endpoint(ws))

        assert ws.closed is not None
        assert ws.closed["code"] == 1008

    @patch("app.api.websocket.authenticate_websocket")
    @patch("app.api.websocket.get_requested_subprotocol")
    @patch("app.modules.rag.generate_answer")
    @patch("app.api.websocket.asyncio.sleep")
    def test_websocket_endpoint_streams_tokens(self, mock_sleep, mock_generate_answer, mock_subprotocol, mock_auth):
        mock_auth.return_value = {"username": "student"}
        mock_subprotocol.return_value = "chat.token"
        mock_generate_answer.return_value = "hello world"
        mock_sleep.return_value = None
        ws = FakeWebSocket(incoming=["what is photosynthesis?", WebSocketDisconnect(code=1000)])

        _run(ws_mod.websocket_endpoint(ws))

        assert ws.accepted is True
        assert ws.accept_subprotocol == "chat.token"
        assert "hello" in ws.sent_texts
        assert "world" in ws.sent_texts


class TestAskWsEndpoint:
    @patch("app.api.websocket.authenticate_websocket")
    def test_websocket_ask_rejects_unauthorized(self, mock_auth):
        mock_auth.return_value = None
        ws = FakeWebSocket()

        _run(ws_mod.websocket_ask(ws))

        assert ws.closed is not None
        assert ws.closed["code"] == 1008

    @patch("app.api.websocket.authenticate_websocket")
    @patch("app.api.websocket.get_requested_subprotocol")
    @patch("app.api.websocket.generate_answer_stream")
    @patch("app.api.websocket.save_chat")
    def test_websocket_ask_streams_chunks_and_end(self, mock_save_chat, mock_stream, mock_subprotocol, mock_auth):
        mock_auth.return_value = {"username": "student"}
        mock_subprotocol.return_value = "chat.token"
        mock_stream.return_value = ["A", "B"]
        payload = json.dumps({"query": "Hi", "session_id": "s1"})
        ws = FakeWebSocket(incoming=[payload, WebSocketDisconnect(code=1000)])

        _run(ws_mod.websocket_ask(ws))

        sent = "\n".join(ws.sent_texts)
        assert '"type": "chunk"' in sent
        assert '"type": "end"' in sent
        mock_save_chat.assert_called()

    @patch("app.api.websocket.authenticate_websocket")
    @patch("app.api.websocket.generate_answer_stream")
    @patch("app.api.websocket.save_chat")
    def test_websocket_ask_fallback_plain_text_input(self, mock_save_chat, mock_stream, mock_auth):
        mock_auth.return_value = {"username": "student"}
        mock_stream.return_value = ["ok"]
        ws = FakeWebSocket(incoming=["plain text question", WebSocketDisconnect(code=1000)])

        _run(ws_mod.websocket_ask(ws))

        mock_save_chat.assert_called()


class TestLessonWsEndpoint:
    @patch("app.api.websocket.authenticate_websocket")
    def test_ws_lesson_rejects_unauthorized(self, mock_auth):
        mock_auth.return_value = None
        ws = FakeWebSocket()

        _run(ws_mod.ws_lesson(ws))

        assert ws.closed is not None
        assert ws.closed["code"] == 1008

    @patch("app.api.websocket.authenticate_websocket")
    @patch("app.api.websocket.get_next_step")
    def test_ws_lesson_sends_complete_when_done(self, mock_get_next_step, mock_auth):
        mock_auth.return_value = {"username": "student"}
        mock_get_next_step.return_value = {"message": "Lesson completed"}
        ws = FakeWebSocket(incoming=[json.dumps({"session_id": "s1"})])

        _run(ws_mod.ws_lesson(ws))

        sent = "\n".join(ws.sent_texts)
        assert '"type": "lesson_complete"' in sent

    @patch("app.api.websocket.authenticate_websocket")
    @patch("app.api.websocket.get_next_step")
    @patch("app.api.websocket.update_step_progress")
    def test_ws_lesson_updates_completed_step(self, mock_update, mock_get_next_step, mock_auth):
        mock_auth.return_value = {"username": "student"}
        mock_get_next_step.side_effect = [
            {"id": 1, "title": "Step 1"},
            {"message": "Lesson completed"},
        ]
        ws = FakeWebSocket(
            incoming=[
                json.dumps({"session_id": "s1"}),
                json.dumps({"action": "complete_step"}),
            ]
        )

        _run(ws_mod.ws_lesson(ws))

        mock_update.assert_called_once_with("student", "s1", 1, "completed")
        sent = "\n".join(ws.sent_texts)
        assert '"type": "lesson_step"' in sent
        assert '"type": "lesson_complete"' in sent


class TestQuizWsEndpoint:
    @patch("app.api.websocket.authenticate_websocket")
    def test_ws_quiz_rejects_unauthorized(self, mock_auth):
        mock_auth.return_value = None
        ws = FakeWebSocket()

        _run(ws_mod.ws_quiz(ws))

        assert ws.closed is not None
        assert ws.closed["code"] == 1008

    @patch("app.api.websocket.authenticate_websocket")
    @patch("app.api.websocket.get_quiz")
    def test_ws_quiz_not_found(self, mock_get_quiz, mock_auth):
        mock_auth.return_value = {"username": "student"}
        mock_get_quiz.return_value = None
        ws = FakeWebSocket(incoming=[json.dumps({"session_id": "s1", "quiz_id": "q1"})])

        _run(ws_mod.ws_quiz(ws))

        sent = "\n".join(ws.sent_texts)
        assert "Quiz not found" in sent

    @patch("app.api.websocket.authenticate_websocket")
    @patch("app.api.websocket.get_quiz")
    @patch("app.api.websocket.submit_quiz_answer")
    def test_ws_quiz_question_feedback_and_complete(self, mock_submit, mock_get_quiz, mock_auth):
        mock_auth.return_value = {"username": "student"}
        mock_get_quiz.return_value = {
            "questions": [
                {"id": "q1", "question": "2+2?", "options": ["3", "4"]},
            ]
        }
        mock_submit.return_value = {"q1": "correct"}
        ws = FakeWebSocket(
            incoming=[
                json.dumps({"session_id": "s1", "quiz_id": "quiz1"}),
                json.dumps({"answer": "4"}),
            ]
        )

        _run(ws_mod.ws_quiz(ws))

        sent = "\n".join(ws.sent_texts)
        assert '"type": "question"' in sent
        assert '"type": "feedback"' in sent
        assert '"type": "quiz_complete"' in sent


class TestAsyncWrapper:
    def test_async_stream_wrapper_yields_tokens(self):
        async def collect():
            out = []
            async for token in ws_mod.async_stream_wrapper(["x", "y"]):
                out.append(token)
            return out

        assert _run(collect()) == ["x", "y"]
