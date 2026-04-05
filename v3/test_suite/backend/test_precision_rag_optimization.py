from app.modules.model_manager import build_prompt
from app.modules.rag import _build_query_variants, _format_context_block, _select_context_top_k
from app.modules.retrieval_orchestrator import hybrid_rank_results


class TestPrecisionRagOptimization:
    def test_select_context_top_k_is_task_tuned_and_bounded(self):
        assert _select_context_top_k("Explain refraction", "qa") == 4
        assert _select_context_top_k("Create a quiz on refraction", "quiz") == 3
        assert _select_context_top_k("Summarize refraction", "summary", summary_context="summary") == 5

    def test_build_query_variants_adds_explanation_rewrites(self):
        variants = _build_query_variants("Explain refraction", "qa")

        assert variants[0] == "Explain refraction"
        assert "refraction definition" in variants
        assert any("explanation" in item for item in variants)

    def test_hybrid_rank_results_filters_chunks_without_signal(self):
        docs = [
            {
                "text": "Refraction is the bending of light when it enters another medium.",
                "source": "knowledge_base/physics/refraction.pdf",
                "index_name": "concept_index",
                "metadata": {"type": "concept", "topic": "Refraction"},
            },
            {
                "text": "Weekly assignment reminder for parents",
                "source": "artifact/reminder.txt",
                "index_name": "qa_index",
                "metadata": {"type": "question", "topic": "Reminder"},
            },
            {
                "text": "General greeting page",
                "source": "misc.txt",
                "index_name": "general_index",
                "metadata": {},
            },
        ]

        ranked = hybrid_rank_results(
            "Explain refraction",
            docs,
            hit_indices=[0],
            hit_distances=[0.05],
            task="lesson",
            top_k=3,
        )

        returned_texts = [item["text"] for item in ranked]
        assert docs[0]["text"] in returned_texts
        assert docs[1]["text"] not in returned_texts
        assert docs[2]["text"] not in returned_texts

    def test_hybrid_rank_results_matches_filter_path_case_insensitively(self):
        docs = [
            {
                "text": "Refraction is the bending of light when it enters another medium.",
                "source": r"D:\GPT\ai-student-companion\v3\knowledge_base\Class X\General Knowledge\TextBooks\Chapter 1 - Light .pdf",
                "index_name": "concept_index",
                "metadata": {"type": "concept", "topic": "Refraction"},
            }
        ]

        ranked = hybrid_rank_results(
            "Explain refraction",
            docs,
            hit_indices=[0],
            hit_distances=[0.05],
            task="lesson",
            top_k=3,
            filter_path=r"d:\GPT\ai-student-companion\v3\knowledge_base\Class X\General Knowledge\TextBooks\Chapter 1 - Light .pdf",
        )

        assert len(ranked) == 1
        assert ranked[0]["text"] == docs[0]["text"]

    def test_context_and_prompt_are_structured_for_teaching(self):
        context = _format_context_block(
            [
                {"text": "Refraction is the bending of light.", "metadata": {"type": "concept", "topic": "Refraction"}},
                {"text": "A straw looks bent in water.", "metadata": {"type": "example", "topic": "Observation"}},
                {"text": "Speed = distance / time", "metadata": {"type": "formula", "topic": "Speed"}},
            ],
            summary_context="Light changes direction between media.",
        )
        prompt = build_prompt(context, "Explain refraction", "", "lesson")

        assert "Concept:" in context
        assert "Example:" in context
        assert "Formula:" in context
        assert "step-by-step like a teacher" in prompt
        assert "ONLY from the provided context" in prompt
