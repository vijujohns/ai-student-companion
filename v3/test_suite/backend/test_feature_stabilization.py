from unittest.mock import MagicMock, patch

from app.core import debug_logger
from app.modules.artifacts import generate_card_quiz
from app.modules.image_pipeline import extract_image_content
from app.modules.ingestion import summarize_pdf
from app.modules.quiz import _normalize_questions, generate_quiz, submit_quiz_answer
from app.modules.model_manager import generate_response, get_model_profiles
from app.modules.rag import generate_answer, retrieve_chunks
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

    @patch("app.modules.quiz.resolve_content_reference")
    @patch("app.modules.quiz.retrieve_chunks")
    @patch("app.modules.quiz.generate_response")
    @patch("app.modules.quiz.get_connection")
    def test_generate_quiz_scopes_retrieval_to_selected_content(self, mock_conn, mock_generate, mock_chunks, mock_resolve):
        fake_conn = MagicMock()
        fake_cursor = MagicMock()
        fake_conn.cursor.return_value = fake_cursor
        mock_conn.return_value = fake_conn
        mock_resolve.return_value = {
            "content_id": "kb:kerala-pdf",
            "path": r"D:\\GPT\\ai-student-companion\\v3\\knowledge_base\\Class X\\General Knowledge\\TextBooks\\Chapter 1 - Kerala.pdf",
            "title": "Chapter 1 - Kerala",
        }
        mock_chunks.return_value = ["Kerala has 14 districts."]
        mock_generate.return_value = '{"questions":[{"question":"How many districts does Kerala have?","options":["12","13","14","15"],"correct_answer":"C","explanation":"The context states Kerala has 14 districts."}]}'

        generate_quiz("student", "session-1", "Chapter 1 - Kerala", num_questions=1, selected_content="kb:kerala-pdf")

        mock_resolve.assert_called_once()
        mock_chunks.assert_called_once_with(
            "Chapter 1 - Kerala",
            filter_path=r"D:\\GPT\\ai-student-companion\\v3\\knowledge_base\\Class X\\General Knowledge\\TextBooks\\Chapter 1 - Kerala.pdf",
        )

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

    @patch("app.modules.quiz.get_connection")
    @patch("app.modules.quiz.retrieve_chunks", return_value=["Kerala is known for Kathakali. Onam is an important festival. The state has 14 districts."])
    @patch(
        "app.modules.quiz.generate_response",
        return_value="""1. Which festival is mentioned in the material?\nA) Onam\nB) Bihu\nC) Pongal\nD) Lohri\nAnswer: A\nExplanation: The context says Onam is an important festival.""",
    )
    def test_generate_quiz_extracts_plain_text_mcqs_before_falling_back(self, mock_generate, mock_chunks, mock_conn):
        fake_conn = MagicMock()
        fake_cursor = MagicMock()
        fake_conn.cursor.return_value = fake_cursor
        mock_conn.return_value = fake_conn

        result = generate_quiz("student", "session-1", "Kerala", num_questions=1)

        assert result["questions"][0]["question"] == "Which festival is mentioned in the material?"
        assert result["questions"][0]["correct_answer"] == "A"
        assert "Onam" in result["questions"][0]["explanation"]

    @patch("app.modules.quiz.get_connection")
    @patch("app.modules.quiz.retrieve_chunks", return_value=["Kerala is known for Kathakali. Onam is an important festival. The state has 14 districts."])
    @patch("app.modules.quiz.generate_response", return_value="I can help with that, but here is a short summary instead of JSON.")
    def test_generate_quiz_uses_grounded_context_fallback_not_placeholder_labels(self, mock_generate, mock_chunks, mock_conn):
        fake_conn = MagicMock()
        fake_cursor = MagicMock()
        fake_conn.cursor.return_value = fake_cursor
        mock_conn.return_value = fake_conn

        result = generate_quiz("student", "session-1", "Kerala", num_questions=2)

        assert len(result["questions"]) == 2
        assert all(not item["question"].lower().startswith("practice question") for item in result["questions"])
        assert any(
            "Kerala" in " ".join(item["options"]) or "Onam" in item["explanation"] or "Kathakali" in item["explanation"]
            for item in result["questions"]
        )

    @patch("app.modules.artifacts.get_connection")
    @patch("app.modules.artifacts.generate_response")
    def test_generate_card_quiz_uses_full_lesson_card_content_as_context(self, mock_generate, mock_conn):
        fake_conn = MagicMock()
        fake_cursor = MagicMock()
        fake_conn.cursor.return_value = fake_cursor
        mock_conn.return_value = fake_conn
        mock_generate.return_value = '{"questions":[{"question":"Which festival is linked with Kerala?","options":["Onam","Bihu","Lohri","Pongal"],"correct_option":"A"}]}'

        card = {
            "card_id": 11,
            "session_id": "lesson-session-1",
            "lesson_plan_id": 7,
            "title": "Festivals of Kerala",
            "content": "Onam is Kerala's most important festival.",
            "bullets": ["Kathakali is a classical art form of Kerala."],
            "numbered": ["Boat races are held during Onam celebrations."],
        }

        result = generate_card_quiz("student", card, num_questions=1, context_hint="Focus on direct recall")

        assert result["payload"]["quiz"][0]["question"] == "Which festival is linked with Kerala?"
        generated_context = mock_generate.call_args.kwargs["context"]
        assert "Onam is Kerala's most important festival." in generated_context
        assert "Kathakali is a classical art form of Kerala." in generated_context
        assert "Boat races are held during Onam celebrations." in generated_context

    @patch("app.modules.quiz.get_connection")
    @patch("app.modules.quiz.get_quiz")
    def test_submit_quiz_answer_accepts_selected_option_text(self, mock_get_quiz, mock_conn):
        fake_conn = MagicMock()
        fake_cursor = MagicMock()
        fake_conn.cursor.return_value = fake_cursor
        mock_conn.return_value = fake_conn
        mock_get_quiz.return_value = {
            "quiz_id": "11",
            "questions": [
                {
                    "id": "q1",
                    "question": "Who founded the Mughal Empire?",
                    "options": ["Babur", "Humayun", "Akbar", "Jahangir"],
                    "correct_option": "A",
                    "correct_answer": "A",
                }
            ],
        }

        result = submit_quiz_answer("student", "session-1", "11", {"q1": "Babur"})

        assert result["q1"]["is_correct"] is True
        assert result["q1"]["correct_answer"] == "Babur"
        assert result["q1"]["user_answer"] == "Babur"

    @patch("app.modules.rag.search", return_value=[])
    @patch("app.modules.rag.documents", [])
    @patch("app.modules.rag.chunk_text", return_value=["Kerala has 14 districts.", "Onam is a major festival in Kerala."])
    @patch("app.modules.rag.extract_text_from_pdf", return_value="Kerala has 14 districts. Onam is a major festival in Kerala.")
    def test_retrieve_chunks_recovers_from_selected_pdf_when_index_has_no_chunks(self, mock_extract, mock_chunk, mock_search):
        file_path = r"D:\\GPT\\ai-student-companion\\v3\\knowledge_base\\Class X\\General Knowledge\\TextBooks\\Chapter 1- Kerala.pdf"

        result = retrieve_chunks("Chapter 1- Kerala", filter_path=file_path, top_k=2)

        assert result == ["Kerala has 14 districts.", "Onam is a major festival in Kerala."]
        mock_extract.assert_called_once_with(file_path)
        mock_chunk.assert_called_once()

    @patch("app.modules.rag.search", return_value=[])
    @patch("app.modules.rag.documents", [])
    @patch("app.modules.rag.os.path.isfile", return_value=True)
    @patch(
        "app.modules.rag.chunk_text",
        side_effect=lambda text, *args, **kwargs: [
            chunk
            for chunk in [
                "The human heart has four chambers." if "four chambers" in str(text) else "",
                "Aorta is the main artery carrying oxygenated blood from the heart." if "Aorta is the main artery" in str(text) else "",
            ]
            if chunk
        ],
    )
    @patch("app.modules.rag.extract_ocr_text_from_pdf", return_value="Aorta is the main artery carrying oxygenated blood from the heart.")
    @patch("app.modules.rag.extract_text_from_pdf", return_value="The human heart has four chambers.")
    def test_retrieve_chunks_uses_pdf_ocr_text_for_diagram_labels(self, mock_extract, mock_ocr, mock_chunk, mock_isfile, mock_search):
        file_path = r"D:\\GPT\\ai-student-companion\\v3\\knowledge_base\\Class X\\General Knowledge\\TextBooks\\Chapter 5 - heart.pdf"

        result = retrieve_chunks("what is aorta", filter_path=file_path, top_k=1)

        assert result == ["Aorta is the main artery carrying oxygenated blood from the heart."]
        mock_extract.assert_called_once_with(file_path)
        mock_ocr.assert_called_once_with(file_path, query="what is aorta")


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

    def test_model_profiles_include_groq_option(self):
        profile_keys = {item["key"] for item in get_model_profiles()}

        assert "groq-cloud" in profile_keys

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-groq-key"}, clear=False)
    @patch("app.modules.model_manager.get_model_config", return_value={
        "type": "cloud",
        "provider": "groq",
        "model_name": "llama-3.1-8b-instant",
        "max_tokens": 120,
        "temperature": 0.2,
    })
    @patch("app.modules.model_manager.resolve_model_name", return_value="groq-llama-fast")
    @patch("app.modules.model_manager.openai")
    def test_generate_response_uses_groq_openai_compatible_client(self, mock_openai, mock_resolve, mock_config):
        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Groq says hello."))]
        )

        result = generate_response("context", "question", task="qa")

        assert result == "Groq says hello."
        mock_openai.OpenAI.assert_called_once_with(
            api_key="test-groq-key",
            base_url="https://api.groq.com/openai/v1",
        )

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

    @patch("app.modules.model_manager.dwarn")
    @patch("app.modules.model_manager.get_model_config", return_value={"type": "local", "path": "models/mock.gguf", "max_tokens": 20, "temperature": 0.2, "n_ctx": 512})
    @patch("app.modules.model_manager.resolve_model_name", return_value="mock-model")
    @patch("app.modules.model_manager._resolve_model_path", return_value="mock.gguf")
    @patch("app.modules.model_manager.get_llm_instance")
    def test_generate_response_logs_selected_model_to_console(self, mock_llm_instance, mock_path, mock_resolve, mock_config, mock_warn):
        mock_llm_instance.return_value = MagicMock(return_value={"choices": [{"text": "Grounded answer"}]})

        result = generate_response("context", "question", task="qa")

        assert result == "Grounded answer"
        assert any(call.args[:2] == ("MODEL", "Model selected for current task") for call in mock_warn.call_args_list)

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

    @patch("app.modules.rag.dwarn")
    @patch("app.modules.rag.get_cache", return_value=None)
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag._retrieve_context_items", return_value=[{"text": "Refraction is the bending of light.", "source": "light.pdf", "metadata": {"type": "concept"}, "score": 0.9}])
    @patch("app.modules.rag.generate_response", return_value="Refraction is the bending of light.")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_logs_selected_context_to_console(self, mock_conn, mock_generate, mock_retrieve, mock_history, mock_save_chat, mock_set_cache, mock_get_cache, mock_warn):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        result = generate_answer("Explain refraction", "user1", "session1")

        assert "Refraction" in result
        assert any(call.args[:2] == ("RAG", "Context selected for current task") for call in mock_warn.call_args_list)

    @patch("app.modules.rag.get_cache", return_value=None)
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag._retrieve_context_items", return_value=[{"text": "Babur founded the Mughal Empire in 1526 after the First Battle of Panipat.", "source": "mughal.pdf", "metadata": {"type": "concept"}, "score": 0.9}])
    @patch("app.modules.rag.generate_response", return_value="Let's find out who Babur is from the provided material. According to the context, Babur founded the Mughal Empire in 1526 after the First Battle of Panipat.")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_rewrites_short_fact_replies_to_be_concise(self, mock_conn, mock_generate, mock_retrieve, mock_history, mock_save_chat, mock_set_cache, mock_get_cache):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        result = generate_answer("who is babur", "user1", "session1")

        assert result.startswith("Babur")
        lowered = result.lower()
        assert "let's find out" not in lowered
        assert "according to the context" not in lowered
        assert "provided material" not in lowered

    @patch("app.modules.rag.get_cache", return_value=None)
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag._retrieve_context_items", return_value=[
        {"text": "Refraction is the bending of light when it passes from one medium to another.", "source": "light.pdf", "metadata": {"type": "concept"}, "score": 0.92},
        {"text": "It happens because the speed of light changes in different media.", "source": "light.pdf", "metadata": {"type": "definition"}, "score": 0.88},
        {"text": "A pencil in water looks bent because of refraction.", "source": "light.pdf", "metadata": {"type": "example"}, "score": 0.84},
    ])
    @patch("app.modules.rag.generate_response", return_value="Refraction is the bending of light when it moves from one medium to another. It changes direction because its speed changes. Common examples include a pencil in water and a rainbow.")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_formats_summary_queries_as_structured_notes(self, mock_conn, mock_generate, mock_retrieve, mock_history, mock_save_chat, mock_set_cache, mock_get_cache):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        result = generate_answer("Summarize refraction for revision notes", "user1", "session1")

        lowered = result.lower()
        assert result.startswith("## 📘")
        assert "### overview" in lowered
        assert "### key points" in lowered
        assert "### final takeaways" in lowered
        assert "pencil in water" in lowered

    @patch("app.modules.rag.get_cache", return_value=None)
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag._retrieve_context_items", return_value=[{"text": "Traditional farming used local seeds and natural manure. Modern farming uses HYV seeds, irrigation, fertilizers, pesticides, and tractors to increase yield.", "source": "farming.pdf", "metadata": {"type": "concept"}, "score": 0.9}])
    @patch("app.modules.rag.generate_response", return_value="Let's break down the concept of modern farming methods step by step, using the provided context. Step 1: Understanding Traditional Farming Methods ... (Chunk 12) Step 2: Introduction to Modern Farming Methods ... (Chunk 17) Step 3: Benefits of Modern Farming Methods ...")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_formats_explanation_queries_into_student_friendly_sections(self, mock_conn, mock_generate, mock_retrieve, mock_history, mock_save_chat, mock_set_cache, mock_get_cache):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        result = generate_answer("Explain modern farming methods", "user1", "session1")

        lowered = result.lower()
        assert result.startswith("## Modern Farming Methods")
        assert "**simple meaning:**" in lowered
        assert "### key points" in lowered
        assert "- " in result
        assert "> **in short:**" in lowered
        assert "chunk" not in lowered
        assert "let's break down" not in lowered

    @patch("app.modules.rag.get_cache", return_value=None)
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag._retrieve_context_items", return_value=[{"text": "Traditional farming used local seeds, natural manure, and less machinery. Modern farming uses HYV seeds, chemical fertilizers, irrigation, and tractors for higher yield.", "source": "farming.pdf", "metadata": {"type": "concept"}, "score": 0.9}])
    @patch("app.modules.rag.generate_response", return_value="Traditional farming used local seeds and natural manure. Modern farming uses HYV seeds, fertilizers, irrigation, and machinery for higher yields.")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_formats_compare_queries_as_markdown_table(self, mock_conn, mock_generate, mock_retrieve, mock_history, mock_save_chat, mock_set_cache, mock_get_cache):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        result = generate_answer("compare traditional farming and modern farming", "user1", "session1")

        assert "| Aspect | Traditional Farming | Modern Farming |" in result
        assert "| Seeds |" in result
        assert "| Yield |" in result

    @patch("app.modules.rag.get_cache", return_value=None)
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag._retrieve_context_items", return_value=[{"text": "The human heart has four parts: Left Atrium, Right Atrium, Left Ventricle, and Right Ventricle.", "source": "heart.pdf", "metadata": {"type": "concept"}, "score": 0.9}])
    @patch("app.modules.rag.generate_response", return_value="Let's look at the provided material to find the answer. According to the material, the human heart has the following parts: - Left Atrium - Right Atrium - Left Ventricle - Right Ventricle. We can see that there are 4 parts mentioned in the material. Therefore, the answer is: 4 (Chunk 1)")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_rewrites_how_many_queries_into_clean_fact_response(self, mock_conn, mock_generate, mock_retrieve, mock_history, mock_save_chat, mock_set_cache, mock_get_cache):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        result = generate_answer("how many parts heart has", "user1", "session1")

        lowered = result.lower()
        assert result.startswith("The human heart has")
        assert "left atrium" in lowered
        assert "right ventricle" in lowered
        assert "let's look at the provided material" not in lowered
        assert "according to the material" not in lowered
        assert "chunk" not in lowered
        assert "provided material" not in lowered

    @patch("app.modules.rag.get_cache", return_value=None)
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag._retrieve_context_items", return_value=[{"text": "The human heart has four parts: Left Atrium, Right Atrium, Left Ventricle, and Right Ventricle. Diagram labels also show Aorta, Pulmonary artery, and Pulmonary veins.", "source": "heart.pdf", "metadata": {"type": "concept"}, "score": 0.9}])
    @patch("app.modules.rag.generate_response", return_value="Let's look at the provided material to find the answer. According to the \"Document Summary\" section, the parts of the heart are listed as: Left Atrium, Right Atrium, Left Ventricle, Right Ventricle. Additionally, in the \"Diagram labels and OCR notes\" section, we can see labels for the heart parts on the diagram.")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_formats_heart_parts_query_as_clean_bullets(self, mock_conn, mock_generate, mock_retrieve, mock_history, mock_save_chat, mock_set_cache, mock_get_cache):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        result = generate_answer("what are parts of heart", "user1", "session1")

        lowered = result.lower()
        assert result.startswith("## Parts of Heart")
        assert "- left atrium" in lowered
        assert "- right ventricle" in lowered
        assert "document summary" not in lowered
        assert "chunk" not in lowered
        assert "provided material" not in lowered

    @patch("app.modules.rag.get_cache", return_value=None)
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag._retrieve_context_items", return_value=[{"text": "Sound waves have characteristics such as frequency, amplitude, wavelength, speed, and period.", "source": "sound.pdf", "metadata": {"type": "concept"}, "score": 0.9}])
    @patch("app.modules.rag.generate_response", return_value="Characteristics of sound waves:\n- Frequency: Label, the number of oscillations or cycles per second\n- Amplitude: Label, the height or loudness of the sound wave\n- Speed: Label, the rate at which the sound wave travels through a medium\n- Wavelength: Label, the distance between two consecutive peaks or troughs of the sound wave\n- Period: Label, the time taken for one complete oscillation or cycle")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_formats_science_characteristics_query_into_clean_bullets(self, mock_conn, mock_generate, mock_retrieve, mock_history, mock_save_chat, mock_set_cache, mock_get_cache):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        result = generate_answer("what are characteristics of sound waves", "user1", "session1")

        lowered = result.lower()
        assert result.startswith("## Characteristics of Sound Waves")
        assert "- frequency:" in lowered
        assert "- amplitude:" in lowered
        assert "label" not in lowered
        assert "> **in short:**" in lowered
        assert "**in short:** -" not in lowered

    @patch("app.modules.rag.get_cache", return_value=None)
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag._retrieve_context_items", return_value=[{"text": "Diagram labels and OCR notes: Aorta Pulmonary artery Pulmonary veins Left ventricle Right ventricle.", "source": "heart.pdf", "metadata": {"type": "concept"}, "score": 0.9}])
    @patch("app.modules.rag.generate_response", return_value="Let's find the answer from the provided context. According to the diagram labels, Aorta is listed as one of the parts of the heart diagram. So, the answer is: Aorta is a part of the heart diagram.")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_asks_student_before_showing_outside_material_explanation(self, mock_conn, mock_generate, mock_retrieve, mock_history, mock_save_chat, mock_set_cache, mock_get_cache):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        result = generate_answer("what is aorta", "user1", "session1")

        lowered = result.lower()
        assert "aorta" in lowered
        assert "general knowledge" not in lowered
        assert "buttons below" not in lowered
        assert "public references" not in lowered

    @patch("app.modules.rag.get_cache", return_value=None)
    @patch("app.modules.rag.set_cache")
    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag._retrieve_context_items", return_value=[{"text": "Diagram labels and OCR notes: Aorta Pulmonary artery Pulmonary veins Right auricle Left auricle Left ventricle Right ventricle. The heart pumps blood throughout the body.", "source": "heart.pdf", "metadata": {"type": "concept"}, "score": 0.9}])
    @patch("app.modules.rag.generate_response", return_value="Let's break down the heart diagram based on the provided context. The heart diagram labels are listed as follows: Aorta, Pulmonary artery, Pulmonary veins, Right auricle, Left auricle, Left ventricle, Right ventricle.")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_formats_diagram_explanation_as_structured_overview(self, mock_conn, mock_generate, mock_retrieve, mock_history, mock_save_chat, mock_set_cache, mock_get_cache):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        result = generate_answer("explain heart diagram", "user1", "session1")

        lowered = result.lower()
        assert result.startswith("## Heart Diagram")
        assert "**simple meaning:**" in lowered
        assert "### key points" in lowered
        assert "- " in result
        assert "**in short:**" in lowered
        assert "let's break down" not in lowered
        assert "provided context" not in lowered

    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag._retrieve_context_items", return_value=[{"text": "Diagram labels and OCR notes: Aorta Pulmonary artery Pulmonary veins Left ventricle Right ventricle.", "source": "heart.pdf", "metadata": {"type": "concept"}, "score": 0.9}])
    @patch("app.modules.rag.generate_response", return_value="Let's find the answer from the provided context. According to the diagram labels, Aorta is listed as one of the parts of the heart diagram. So, the answer is: Aorta is a part of the heart diagram.")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_shows_outside_material_explanation_after_student_says_yes(self, mock_conn, mock_generate, mock_retrieve, mock_history, mock_save_chat):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        cache_store = {}

        def fake_get_cache(key):
            return cache_store.get(key)

        def fake_set_cache(key, value):
            cache_store[key] = value
            return True

        def fake_delete_cache(key):
            cache_store.pop(key, None)
            return True

        with (
            patch("app.modules.rag.get_cache", side_effect=fake_get_cache),
            patch("app.modules.rag.set_cache", side_effect=fake_set_cache),
        ):
            first = generate_answer("what is aorta", "user1", "session1")
            second = generate_answer("yes", "user1", "session1")

        assert "general knowledge" not in first.lower()
        lowered = second.lower()
        assert "extra explanation" not in lowered
        assert "public references" not in lowered
        assert "aorta" in first.lower()
        assert "don't have enough information in the provided material" in lowered

    @patch("app.modules.rag.save_chat")
    @patch("app.modules.rag.get_history", return_value=[])
    @patch("app.modules.rag._retrieve_context_items", return_value=[{"text": "Diagram labels and OCR notes: Aorta Pulmonary artery Pulmonary veins Right auricle Left auricle Left ventricle Right ventricle. The heart pumps blood throughout the body.", "source": "heart.pdf", "metadata": {"type": "concept"}, "score": 0.9}])
    @patch("app.modules.rag.generate_response", return_value="Let's break down the heart diagram based on the provided context. The heart diagram labels are listed as follows: Aorta, Pulmonary artery, Pulmonary veins, Right auricle, Left auricle, Left ventricle, Right ventricle.")
    @patch("app.modules.rag.get_connection")
    def test_generate_answer_diagram_explanation_yes_returns_structured_part_help(self, mock_conn, mock_generate, mock_retrieve, mock_history, mock_save_chat):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db

        cache_store = {}

        def fake_get_cache(key):
            return cache_store.get(key)

        def fake_set_cache(key, value):
            cache_store[key] = value
            return True

        def fake_delete_cache(key):
            cache_store.pop(key, None)
            return True

        with (
            patch("app.modules.rag.get_cache", side_effect=fake_get_cache),
            patch("app.modules.rag.set_cache", side_effect=fake_set_cache),
        ):
            first = generate_answer("explain heart diagram", "user1", "session1")
            second = generate_answer("yes", "user1", "session1")

        assert first.startswith("## Heart Diagram")
        lowered = second.lower()
        assert "extra explanation" not in lowered
        assert "public references" not in lowered
        assert "don't have enough information in the provided material" in lowered
