# Module Analysis: Backend AI and Retrieval

## `modules/rag.py`

- Purpose: Main QA pipeline.
- Inputs: query, user id, session id, model name/profile, selected content reference, task, user level, cache bypass flag.
- Outputs: final answer string or streamed token payloads; chat history persistence.
- Internal logic:
  - Resolves session scope and selected content through `file_management`.
  - Reads recent history.
  - Builds query variants and retrieves FAISS context.
  - Applies selected-file recovery when semantic search is weak.
  - Limits context to token budget.
  - Builds cache key by user/session/query/model/content/task/user level.
  - Generates answer through `model_manager`.
  - Validates grounding and falls back when answer is ungrounded/no-info.
  - Applies deterministic formatter before delivery.
- Dependencies:
  - Internal: answer formatter, cache, DB, FAISS search, content references, history, ingestion summaries, model manager, query classifier, retrieval orchestrator, debug logger, config loader.
  - External: hashlib, regex, functools.
- Interactions:
  - REST `/ask` and WS `/ws/ask` call this for QA and non-generator tasks.
  - Lesson/quiz/assessment reuse `retrieve_chunks`.
- Risks/tech debt:
  - Very large module with retrieval, prompt context assembly, grounding, formatting, cache policy, and fallback all together.
  - Regex/heuristic-heavy answer grounding can reject valid paraphrases or accept shallow overlap.
  - Cache disabled in dev; production cache behavior may be less exercised locally.
  - Follow-up detection is simple and session-history dependent.
- Tests:
  - RAG, precision optimization, retrieval upgrade, e2e, contract tests.

## `modules/model_manager.py`

- Purpose: model inventory, profile-controlled task selection, prompt construction, generation.
- Inputs: task/query/context/history, optional model name, active profile, settings/env.
- Outputs: model name, prompt, generated text/stream chunks.
- Internal logic:
  - Reads model profiles from config and active profile from `app_settings`.
  - Chooses preferred task model with fallback candidates.
  - Loads local GGUF models lazily through llama-cpp and caches instances by path.
  - Supports cloud providers with OpenAI-compatible clients for OpenAI/Groq.
  - Adjusts temperature/token budget by task and question type.
  - Builds strict system/user prompts for grounded educational answers.
- Dependencies: config loader, query classifier, debug logger, DB, llama-cpp, OpenAI-compatible SDK.
- Interactions:
  - Used by RAG, lesson plans, quizzes, flashcards, assessment, image pipeline, utility executor.
- Risks/tech debt:
  - In-process local model cache can consume large RAM and is not eviction-aware.
  - Per-model locking serializes generation per model.
  - Cloud provider names/models in config may drift over time.
  - Prompt rules are embedded in code, not versioned as prompt assets.
- Tests:
  - Indirect through generator, lesson, quiz, RAG, admin model-profile tests.

## `modules/faiss_store.py`

- Purpose: vector index and metadata store.
- Inputs: document chunks, embeddings, search query/filter.
- Outputs: FAISS index files, metadata/documents, search results.
- Internal logic:
  - Lazily loads sentence transformer embedding model.
  - Maintains `documents`, FAISS index, logical index metadata.
  - Adds/removes docs by source and persists index/metadata.
  - Runs hybrid reranking through retrieval orchestrator.
- Dependencies: FAISS, numpy, pickle/json, sentence-transformers, config, retrieval orchestrator.
- Interactions:
  - Ingestion writes documents.
  - RAG, generator executor, retrieval helpers read search results.
- Risks:
  - Module-level global mutable state with persistence side effects.
  - Index rebuild/remove operations need careful locking under concurrent indexing/search.
  - Embedding model download/load can be slow and fragile offline.
- Tests:
  - RAG/retrieval/smart reindexing tests.

## `modules/retrieval_orchestrator.py`

- Purpose: retrieval planning and reranking.
- Inputs: query, candidate documents, task.
- Outputs: ranked/cleaned chunks and context packets.
- Internal logic:
  - Infers source type and index plan.
  - Applies tokenization, lexical score, semantic score normalization, intent bonuses, boilerplate filtering.
  - Builds context packets for downstream prompting.
- Risks:
  - Heuristic score tuning may be hard to reason about and test exhaustively.
  - Query classifier coupling means changes in one file alter retrieval behavior.
- Tests:
  - Retrieval upgrade, precision RAG optimization, smart reindexing.

## `modules/answer_formatter.py`

- Purpose: deterministic formatting and cleanup after model output.
- Inputs: raw answer and query.
- Outputs: concise formatted answer.
- Internal logic:
  - Detects definition/fact/list/explain/compare/summary intents.
  - Deduplicates fragments, creates bullets, trims word count, removes context markers.
- Risks:
  - Can over-normalize legitimate educational nuance.
  - Duplicates some logic from RAG and query classifier.
- Tests:
  - Low coverage/module and RAG tests likely cover paths indirectly.

## `modules/query_classifier.py`

- Purpose: lightweight intent classification.
- Inputs: query string.
- Outputs: intent such as summary, quote, definition, list, math, etc.
- Risks: regex rules are brittle for multilingual/natural language variation.
- Tests: task/router and RAG tests.

## `modules/task_router.py`

- Purpose: normalize explicit/implicit task routing.
- Inputs: route, query, requested task/mode, model name, content id.
- Outputs: `TaskRoute` dataclass with task/scope/explicitness.
- Risks: task inference overlaps with RAG's own `_infer_retrieval_task`.
- Tests: `test_task_router.py`.

## Executors

- `generator_executor.py`: handles explicit summary/quiz/flashcard style generation from selected content or FAISS search.
- `utility_executor.py`: dispatches math, translation, explorer tasks.
- `math_executor.py`: normalizes math expressions and can ask model for solution formatting.
- `translation.py` and `translation_executor.py`: translate text, list supported languages, parse translation requests.

Risks across executors:

- Task names and frontend `task/mode` values must stay aligned.
- Some utility paths fall back to model generation, so they inherit model latency and grounding limitations.

Tests:

- Generator executor, math/translation executor, accessibility/multilingual, task router.
