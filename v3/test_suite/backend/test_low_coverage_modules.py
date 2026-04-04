"""Targeted tests for low-coverage backend modules."""

import asyncio
import json
import sqlite3
from unittest.mock import MagicMock, patch, mock_open

import pytest

from app.core import config_loader
from app.modules import db as db_module, ingestion, model_manager, policy, progress, translation, ws_auth


class _FakeWebSocket:
    def __init__(self, headers=None, query=None):
        self.headers = headers or {}
        self.query_params = query or {}
        self.closed = None

    async def close(self, code=None, reason=None):
        self.closed = {"code": code, "reason": reason}


class TestWsAuth:
    def test_get_token_from_authorization_header(self):
        ws = _FakeWebSocket(headers={"authorization": "bearer abc.def.ghi"})
        token = asyncio.run(ws_auth.get_token_from_websocket(ws))
        assert token == "abc.def.ghi"

    def test_get_token_from_cookie_header(self):
        ws = _FakeWebSocket(headers={"cookie": "theme=dark; access_token=cookie.jwt.token; mode=study"})
        token = asyncio.run(ws_auth.get_token_from_websocket(ws))
        assert token == "cookie.jwt.token"

    def test_get_token_from_subprotocol(self):
        ws = _FakeWebSocket(headers={"sec-websocket-protocol": "other, chat.tok.en.sig"})
        token = asyncio.run(ws_auth.get_token_from_websocket(ws))
        assert token == "tok.en.sig"

    def test_get_token_from_query_param_fallback_disabled_by_default(self):
        ws = _FakeWebSocket(query={"token": "legacy-token"})
        token = asyncio.run(ws_auth.get_token_from_websocket(ws))
        assert token is None

    def test_get_token_returns_none_when_missing(self):
        ws = _FakeWebSocket()
        token = asyncio.run(ws_auth.get_token_from_websocket(ws))
        assert token is None

    def test_get_requested_subprotocol(self):
        ws = _FakeWebSocket(headers={"sec-websocket-protocol": "foo, chat.jwt.token"})
        assert ws_auth.get_requested_subprotocol(ws) == "chat.jwt.token"

    def test_get_requested_subprotocol_none(self):
        ws = _FakeWebSocket(headers={"sec-websocket-protocol": "foo,bar"})
        assert ws_auth.get_requested_subprotocol(ws) is None

    @patch("app.modules.ws_auth.verify_token")
    def test_authenticate_websocket_success(self, mock_verify):
        mock_verify.return_value = {"username": "student"}
        ws = _FakeWebSocket(headers={"authorization": "bearer token123"})
        user = asyncio.run(ws_auth.authenticate_websocket(ws))
        assert user == {"username": "student"}

    @patch("app.modules.ws_auth.verify_token")
    def test_authenticate_websocket_none_without_token(self, mock_verify):
        ws = _FakeWebSocket()
        user = asyncio.run(ws_auth.authenticate_websocket(ws))
        assert user is None
        mock_verify.assert_not_called()

    @patch("app.modules.ws_auth.authenticate_websocket")
    def test_require_websocket_auth_closes_unauthorized(self, mock_auth):
        mock_auth.return_value = None
        ws = _FakeWebSocket()
        result = asyncio.run(ws_auth.require_websocket_auth(ws))
        assert result is None
        assert ws.closed is not None
        assert ws.closed["code"] == 1008


class TestPolicy:
    def test_consume_quota_blocks_until_period_expires(self, tmp_path):
        db_path = tmp_path / "policy-test.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE users (
                username TEXT PRIMARY KEY,
                plan_code TEXT,
                plan_started_at TEXT,
                plan_expires_at TEXT,
                auto_renew INTEGER,
                is_trial INTEGER,
                trial_ends_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE usage_counters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                period_start TEXT,
                period_end TEXT,
                uploads_count INTEGER DEFAULT 0,
                quiz_count INTEGER DEFAULT 0,
                flashcard_count INTEGER DEFAULT 0,
                lesson_count INTEGER DEFAULT 0,
                ask_count INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO users (username, plan_code, plan_started_at, auto_renew, is_trial, trial_ends_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("student", "free", "2024-01-01T00:00:00+00:00", 0, 1, "2024-01-08T00:00:00+00:00"),
        )
        conn.commit()

        timestamps = iter(
            [
                policy.datetime(2024, 1, 1, tzinfo=policy.UTC),
                policy.datetime(2024, 1, 1, tzinfo=policy.UTC),
                policy.datetime(2024, 1, 8, tzinfo=policy.UTC),
                policy.datetime(2024, 1, 8, tzinfo=policy.UTC),
            ]
        )

        conn.close()

        with patch("app.modules.policy.get_connection", side_effect=lambda: sqlite3.connect(db_path)), patch("app.modules.policy._utc_now", side_effect=lambda: next(timestamps)):
            assert policy.consume_quota("student", "upload") == (True, "MSG-1000")
            assert policy.consume_quota("student", "upload") == (False, "MSG-1201")
            assert policy.consume_quota("student", "upload") == (True, "MSG-1000")

        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT uploads_count FROM usage_counters ORDER BY id").fetchall()
        assert rows == [(1,), (1,)]
        conn.close()


class TestProgress:
    @patch("app.modules.progress.get_connection")
    def test_record_progress_inserts_and_commits(self, mock_conn_factory):
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn_factory.return_value = conn

        result = progress.record_progress("u1", "s1", 2, "completed")

        assert result == {"status": "updated"}
        cursor.execute.assert_called_once()
        conn.commit.assert_called_once()
        conn.close.assert_called_once()

    @patch("app.modules.progress.get_connection")
    def test_get_latest_step_status_found(self, mock_conn_factory):
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = ("completed",)
        conn.cursor.return_value = cursor
        mock_conn_factory.return_value = conn

        result = progress.get_latest_step_status("u1", "s1", 1)
        assert result == "completed"

    @patch("app.modules.progress.get_connection")
    def test_get_latest_step_status_none(self, mock_conn_factory):
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        conn.cursor.return_value = cursor
        mock_conn_factory.return_value = conn

        result = progress.get_latest_step_status("u1", "s1", 1)
        assert result is None

    @patch("app.modules.progress.get_connection")
    def test_get_completed_step_ids_returns_latest_completed_only(self, mock_conn_factory):
        conn = MagicMock()
        cursor = MagicMock()
        # step 1 becomes in_progress later; step 2 stays completed
        cursor.fetchall.return_value = [
            (1, "completed"),
            (2, "completed"),
            (1, "in_progress"),
        ]
        conn.cursor.return_value = cursor
        mock_conn_factory.return_value = conn

        result = progress.get_completed_step_ids("u1", "s1")
        assert result == [2]

    @patch("app.modules.progress.get_connection")
    def test_reset_progress_deletes_and_commits(self, mock_conn_factory):
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn_factory.return_value = conn

        result = progress.reset_progress("u1", "s1")

        assert result == {"status": "progress reset"}
        cursor.execute.assert_called_once()
        conn.commit.assert_called_once()
        conn.close.assert_called_once()


class TestTranslation:
    @patch("app.modules.translation.GoogleTranslator")
    def test_translate_success(self, mock_translator):
        mock_instance = MagicMock()
        mock_instance.translate.return_value = "hello"
        mock_translator.return_value = mock_instance

        assert translation.translate("namaste", target="en") == "hello"
        mock_translator.assert_called_once_with(source="auto", target="en")

    @patch("app.modules.translation.GoogleTranslator")
    def test_translate_fallback_dict_hit(self, mock_translator):
        mock_instance = MagicMock()
        mock_instance.translate.side_effect = Exception("network")
        mock_translator.return_value = mock_instance

        assert translation.translate("namaste", target="en") == "hello"

    @patch("app.modules.translation.GoogleTranslator")
    def test_translate_fallback_original_text(self, mock_translator):
        mock_instance = MagicMock()
        mock_instance.translate.side_effect = Exception("network")
        mock_translator.return_value = mock_instance

        assert translation.translate("bonjour", target="en") == "bonjour"


class TestConfigLoader:
    @patch("app.core.config_loader.load_config")
    def test_get_backend_bind_config_prefers_environment_variables(self, mock_load_config, monkeypatch):
        mock_load_config.return_value = {
            "network": {
                "backend": {
                    "bind_host": "127.0.0.1",
                    "port": 8000,
                }
            }
        }
        monkeypatch.setenv("BACKEND_HOST", "0.0.0.0")
        monkeypatch.setenv("PORT", "8015")

        bind = config_loader.get_backend_bind_config()

        assert bind == {"host": "0.0.0.0", "port": 8015}


class TestIngestion:
    @patch("app.modules.ingestion.PdfReader")
    def test_extract_text_from_pdf_strips_whitespace(self, mock_reader_cls):
        reader = MagicMock()
        page1 = MagicMock()
        page2 = MagicMock()
        page1.extract_text.return_value = "Hello\n\n"
        page2.extract_text.return_value = " World"
        reader.pages = [page1, page2]
        mock_reader_cls.return_value = reader

        result = ingestion.extract_text_from_pdf("dummy.pdf")
        assert result == "Hello World"

    def test_chunk_text_splits_with_overlap(self):
        text = "A" * 1200
        chunks = ingestion.chunk_text(text, chunk_size=500, overlap=100)
        assert len(chunks) >= 2
        assert all(isinstance(c, str) and c for c in chunks)

    def test_chunk_text_prefers_sentence_boundary(self):
        text = ("Sentence one. " * 30) + "Tail"
        chunks = ingestion.chunk_text(text, chunk_size=180, overlap=20)
        assert len(chunks) >= 1
        # At least one early chunk should end in a period due to boundary logic
        assert any(c.endswith(".") for c in chunks[:-1] or chunks)

    @patch("app.modules.ingestion.os.makedirs")
    @patch("app.modules.ingestion.os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data='{"x.pdf":"old"}')
    def test_save_summary_merges_existing(self, mock_file, mock_exists, mock_makedirs):
        mock_exists.return_value = True

        with patch("app.modules.ingestion.SUMMARY_FILE", "summary.json"):
            ingestion.save_summary("new.pdf", "new summary")

        # Ensure writes happened and includes new key
        handle = mock_file()
        written = "".join(call.args[0] for call in handle.write.mock_calls)
        parsed = json.loads(written)
        assert parsed["x.pdf"] == "old"
        assert parsed["new.pdf"] == "new summary"
        mock_makedirs.assert_called_once()

    @patch("app.modules.ingestion.os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data='{"a.pdf":"A summary"}')
    def test_get_summary_returns_value(self, mock_file, mock_exists):
        mock_exists.return_value = True
        with patch("app.modules.ingestion.SUMMARY_FILE", "summary.json"):
            assert ingestion.get_summary("a.pdf") == "A summary"

    @patch("app.modules.ingestion.os.path.exists")
    def test_get_summary_returns_empty_if_missing(self, mock_exists):
        mock_exists.return_value = False
        assert ingestion.get_summary("missing.pdf") == ""

    @patch("app.modules.model_manager.generate_response")
    def test_safe_summarize_handles_long_input(self, mock_generate):
        mock_generate.return_value = "mini summary"
        text = "x" * 4000

        result = ingestion.safe_summarize(text, "doc.pdf", model_name="m1", chunk_index=1)

        assert "mini summary" in result
        assert mock_generate.call_count >= 2

    @patch("app.modules.model_manager.generate_response")
    def test_combine_summaries_reduces_to_single(self, mock_generate):
        mock_generate.side_effect = ["combined-1", "combined-final"]
        result = ingestion.combine_summaries(["a", "b", "c", "d"], model_name="m1")
        assert isinstance(result, str)

    @patch("app.modules.ingestion.extract_text_from_pdf")
    @patch("app.modules.ingestion.summarize_pdf")
    @patch("app.modules.ingestion.chunk_text")
    @patch("app.modules.faiss_store.add_doc")
    def test_ingest_pdf_runs_pipeline(self, mock_add_doc, mock_chunk_text, mock_summarize, mock_extract):
        mock_extract.return_value = "Some extracted text"
        mock_chunk_text.return_value = ["c1", "c2"]

        ingestion.ingest_pdf("book.pdf", model_name="m1")

        mock_extract.assert_called_once_with("book.pdf")
        mock_summarize.assert_called_once()
        assert mock_add_doc.call_count == 2


class _TrackingLock:
    def __init__(self):
        self.depth = 0

    def __enter__(self):
        self.depth += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        self.depth -= 1


class TestModelManager:
    def test_decide_model_uses_fastest_profile_for_quiz(self):
        with patch("app.modules.model_manager.get_active_model_profile_key", return_value="fastest"), \
             patch("app.modules.model_manager.is_model_available", return_value=True):
            assert model_manager.decide_model("quiz", "Generate 5 questions", "short context") == "tinyllama-1.1b-chat"

    def test_decide_model_uses_balanced_profile_for_assessment(self):
        with patch("app.modules.model_manager.get_active_model_profile_key", return_value="balanced"), \
             patch("app.modules.model_manager.is_model_available", return_value=True):
            assert model_manager.decide_model("quiz", "Create an exam paper with reasoning", "longer classroom context") == "phi-4"

    @patch("app.modules.model_manager.get_model_config")
    @patch("app.modules.model_manager.get_llm_instance")
    @patch("app.modules.model_manager._get_llm_lock")
    @patch("app.modules.model_manager._resolve_model_path")
    def test_generate_response_local_holds_model_lock(
        self,
        mock_resolve_model_path,
        mock_get_lock,
        mock_get_llm_instance,
        mock_get_model_config,
    ):
        lock = _TrackingLock()
        observed = {}

        def fake_llm(*args, **kwargs):
            observed["depth_during_call"] = lock.depth
            return {"choices": [{"text": " answer "}]}

        mock_resolve_model_path.return_value = "fake-model.gguf"
        mock_get_lock.return_value = lock
        mock_get_llm_instance.return_value = fake_llm
        mock_get_model_config.return_value = {
            "type": "local",
            "max_tokens": 64,
            "temperature": 0.3,
            "n_ctx": 2048,
            "path": "models/fake.gguf",
        }

        result = model_manager.generate_response("context", "question", model_name="mistral-7b")

        assert result == "answer"
        assert observed["depth_during_call"] == 1
        assert lock.depth == 0

    @patch("app.modules.model_manager.get_model_config")
    @patch("app.modules.model_manager.get_llm_instance")
    @patch("app.modules.model_manager._get_llm_lock")
    @patch("app.modules.model_manager._resolve_model_path")
    def test_generate_response_stream_holds_lock_during_iteration(
        self,
        mock_resolve_model_path,
        mock_get_lock,
        mock_get_llm_instance,
        mock_get_model_config,
    ):
        lock = _TrackingLock()
        observed_depths = []

        def fake_stream(*args, **kwargs):
            def iterator():
                observed_depths.append(lock.depth)
                yield {"choices": [{"text": "one "}]}
                observed_depths.append(lock.depth)
                yield {"choices": [{"text": "two"}]}

            return iterator()

        mock_resolve_model_path.return_value = "fake-model.gguf"
        mock_get_lock.return_value = lock
        mock_get_llm_instance.return_value = fake_stream
        mock_get_model_config.return_value = {
            "type": "local",
            "max_tokens": 64,
            "temperature": 0.3,
            "n_ctx": 2048,
            "path": "models/fake.gguf",
        }

        result = list(model_manager.generate_response_stream("context", "question", model_name="mistral-7b"))

        assert result == ["one ", "two"]
        assert observed_depths == [1, 1]
        assert lock.depth == 0


class TestDbHelpers:
    @patch("app.modules.db.get_connection")
    def test_execute_query_raises_when_requested(self, mock_conn_factory):
        conn = MagicMock()
        cursor = MagicMock()
        cursor.execute.side_effect = sqlite3.OperationalError("db locked")
        conn.cursor.return_value = cursor
        mock_conn_factory.return_value = conn

        with pytest.raises(sqlite3.OperationalError):
            db_module.execute_query("SELECT 1", raise_on_error=True)

        conn.close.assert_called_once()

    @patch("app.modules.db.execute_query")
    def test_safe_fetch_uses_raise_on_error(self, mock_execute_query):
        mock_execute_query.return_value = [{"id": 1, "name": "row"}]

        result = db_module.safe_fetch("SELECT * FROM demo")

        assert result == [{"id": 1, "name": "row"}]
        mock_execute_query.assert_called_once_with("SELECT * FROM demo", None, fetch=True, raise_on_error=True)
