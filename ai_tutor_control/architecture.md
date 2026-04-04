# Step 1 - Codebase Discovery

Date: 2026-04-04
Status: Documented and awaiting approval.

## File Structure Overview
- `v3/backend/run.py` — uvicorn launcher.
- `v3/backend/app/main.py` — FastAPI app setup, middleware, exception handlers, startup lifecycle.
- `v3/backend/app/api/routes.py` — primary REST surface.
- `v3/backend/app/api/websocket.py` — streaming WebSocket surface.
- `v3/backend/app/modules/` — domain logic: auth, RAG, ingestion, quizzes, lessons, analytics, subscriptions, OCR, translation.
- `v3/backend/app/modules/adapters/default_services.py` + `modules/interfaces/service_ports.py` — service registry and domain ports.
- `v3/backend/models/` — local `.gguf` models.
- `v3/configs/settings.json` — model, RAG, network, and CORS configuration.
- `v3/data/` — FAISS index and metadata.
- `v3/frontend/src/` — React app split into `components/`, `hooks/`, `services/`, and `utils/`.

## Backend Truth Map

### Entrypoints and Startup
1. `v3/backend/run.py` launches `uvicorn.run("app.main:app", ...)`.
2. `v3/backend/app/main.py` creates the `FastAPI` app.
3. Startup lifespan runs:
   - `load_index()` from `faiss_store.py`
   - background `load_knowledge_base()` from `kb_sync.py`
   - `init_db()` from `db.py`
   - `recover_indexing_jobs()` from `file_management.py`
4. Routers registered:
   - REST: `app.include_router(router)`
   - WebSocket: `app.include_router(websocket_router)`

### API Route Groups (`v3/backend/app/api/routes.py`)
- Runtime: `/health/runtime`
- Chat: `/ask`, `/history`
- Auth/Profile: `/login`, `/auth/session`, `/logout`, `/register`, `/profile`, `/reset-password`
- Relationships & collaboration: `/relationships/*`, `/students/*`, `/collaboration/notes`
- Session management: `/sessions/*`
- File and content access: `/files/*`, `/pdf`, `/upload/file`, `/ocr/status`
- Knowledge browsing: `/classes`, `/subjects`, `/folders`, `/contents`
- Learning flows: `/lesson-plan/*`, `/quiz/*`, `/flashcards/*`, `/artifacts/*`
- Assessment and progress: `/assessment/*`, `/progress/*`
- Preferences and language: `/languages`, `/translate`, `/preferences`
- Commercial/admin: `/plan/*`, `/subscription/*`, `/admin/reindex*`, `/admin/model-profiles`

### WebSocket Endpoints (`v3/backend/app/api/websocket.py`)
- `/ws` — authenticated basic streaming test endpoint
- `/ws/ask` — authenticated streaming RAG chat
- `/ws/lesson` — interactive lesson-step loop
- `/ws/quiz` — interactive quiz loop with feedback

### Service Domains (`ServiceRegistry`)
Defined in `v3/backend/app/modules/adapters/default_services.py`:
- `identity`
- `relationships`
- `progress`
- `knowledge`
- `commercial`
- `learning`

## RAG and Retrieval Pipeline

### Ingestion Path
1. Source PDFs come from `v3/knowledge_base/` and user uploads under `v3/backend/app/uploads/`.
2. `ingestion.py`:
   - extracts text with `pypdf`
   - chunks text using RAG settings from `v3/configs/settings.json`
   - writes document summaries to `v3/data/pdf_summaries.json`
   - sends chunks to `faiss_store.add_doc()`
3. `kb_sync.py` handles full/incremental reindex scans and persists metadata.

### Retrieval/Answer Path
1. `rag.generate_answer()` or `rag.generate_answer_stream()` receives the query.
2. Cache lookup occurs first.
3. Recent chat history and optional session content reference are resolved.
4. `faiss_store.search()` retrieves top chunks from the FAISS index.
5. `rank_chunks()` reorders context.
6. `model_manager.generate_response()` / `generate_response_stream()` runs the selected model.
7. `history.save_chat()` persists the final answer back to SQLite.
8. The result is cached and returned/streamed.

### Retrieval Consumers
- `lesson_plan.py`
- `quiz.py`
- `assessment.py`

These modules reuse `rag.retrieve_chunks()` for chapter or subject context.

## Model Inventory
Configured in `v3/backend/app/modules/model_manager.py` and `v3/configs/settings.json`.

### Local GGUF Models
- `tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf`
- `mistral-7b-instruct-v0.2.Q4_K_M.gguf`
- `Qwen2.5-7B-Instruct-Q4_K_M.gguf`
- `phi-4-Q4_K_M.gguf`
- `Meta-Llama-3-8B-Instruct-Q4_K_M.gguf`

### Optional Cloud Model
- `gpt-3.5-turbo`

### Active Defaults
- Default model: `qwen2.5-7b`
- Active profile: `balanced`
- Task mapping:
  - `qa` -> `qwen2.5-7b`
  - `lesson` -> `qwen2.5-7b`
  - `quiz` -> `phi-4`
  - `flashcards` -> `qwen2.5-7b`
  - `summary` -> `mistral-7b`

## Dependency Graph Summary
- Main dependency spine: `run.py` -> `main.py` -> `api/*` -> `modules/*` + `schemas/*`.
- Most central runtime files are:
  - `v3/backend/app/api/routes.py`
  - `v3/backend/app/modules/rag.py`
  - `v3/backend/app/modules/model_manager.py`
  - `v3/backend/app/modules/db.py`
  - `v3/backend/app/modules/file_management.py`
- Existing static graph documentation in `v3/docs/python-dependency-graph.md` reports one notable cycle:
  - `faiss_store.py` <-> `ingestion.py`

## Runtime Flow Summary

### Chat Runtime
`frontend/src/components/ChatPanel.jsx` -> `frontend/src/services/websocket.js` -> `/ws/ask` -> `rag.generate_answer_stream()` -> FAISS retrieval + model generation -> `history.save_chat()` -> streamed tokens back to UI.

### HTTP Ask Runtime
`frontend/src/services/api.js` -> `POST /ask` -> `routes.ask()` -> `rag.generate_answer()` -> cache/history/FAISS/model -> envelope response.

### Upload and Index Runtime
`POST /files/upload` -> `file_management.upload_file()` -> filesystem write + DB status rows -> background indexing job -> `ingestion.ingest_pdf()` / `ingest_image()` -> FAISS update.

### Lesson and Quiz Runtime
- `POST /lesson-plan/create` -> `lesson_plan.generate_lesson_plan()` -> RAG retrieval -> model generation -> persist lesson plan and lesson cards.
- `POST /quiz/generate` -> `quiz.generate_quiz()` -> RAG retrieval -> model generation -> persist quiz session/results.

## Step 1 Conclusion
Codebase discovery is complete and documented here. Approval is required before Step 1 can be marked completed in the execution plan.

## Step 2 - Gap Analysis

Date: 2026-04-04
Status: Documented and awaiting approval.

### Comparison Against Required Features

| Feature Area | Required Capability | Current Status | Evidence | Gap Summary |
|---|---|---|---|---|
| Auth + session control | Secure login, role checks, session ownership, WS auth | **Supported** | `api/routes.py`, `modules/auth.py`, `modules/dependencies.py`, `modules/ws_auth.py` | Baseline is already in place and production-shaped. |
| Chat + streaming tutor | HTTP/WS tutoring with persistence and quotas | **Supported** | `/ask`, `/ws/ask`, `rag.py`, `history.py`, `policy.py` | Core tutor flow exists and is usable now. |
| Task router | Explicit request-to-task dispatching across domains | **Partial** | `model_manager.py` has task-based model selection; `ServiceRegistry` exists in `adapters/default_services.py` | No dedicated intent router/orchestrator currently decides whether a request should go to Q&A, lesson, quiz, translation, or future math handling. |
| Retrieval upgrade | Strong retrieval quality, extensibility, and source grounding | **Partial** | `faiss_store.py`, `rag.py`, `kb_sync.py`, `ingestion.py` | FAISS retrieval, filtering, summaries, and chunk ranking exist, but there is no hybrid lexical+semantic retrieval, reranker, or citation-confidence layer. |
| Generators | Lesson, quiz, flashcard, and assessment generation | **Supported** | `lesson_plan.py`, `quiz.py`, `flashcards.py`, `assessment.py`, `artifacts.py` | Generator coverage is broad; remaining gap is orchestration consistency rather than feature absence. |
| Image pipeline | File upload, OCR ingestion, and image-aware learning flow | **Partial** | `ocr.py`, `ingestion.py::ingest_image`, `/ocr/status`, `/upload/file` | OCR-based ingestion exists, but true multimodal reasoning/diagram interpretation is not present yet. |
| Translation | Language listing and text translation support | **Supported** | `translation.py`, `/languages`, `/translate`, `/preferences` | Baseline multilingual utility is present. |
| Math handling | Dedicated math-solving / validation path | **Missing** | No dedicated math module or symbolic solver found in backend search | Mathematics currently depends on the generic LLM path rather than a domain-specific solver or verifier. |
| Subscription/commercial controls | Catalog, quoting, activation, entitlements | **Partial** | `subscriptions.py`, `/subscription/catalog`, `/subscription/quote`, `/subscription/activate` | Commercial groundwork exists, but the lifecycle is still app-internal and not a full billing platform integration. |
| Progress + collaboration | Analytics, mastery, teacher/parent access, notes | **Supported** | `analytics.py`, relationship/collaboration routes, role-based panels | These product areas are already materially implemented. |

### Classification Summary

#### Supported
- Authentication and authorization
- Session management and streaming chat
- Lesson, quiz, flashcard, and assessment generators
- Translation baseline
- Progress analytics and collaboration roles

#### Partial
- Task routing/orchestration
- Retrieval quality upgrade
- Image pipeline beyond OCR
- Subscription/commercial lifecycle depth

#### Missing
- Dedicated math engine / solver / validator path

### Step 2 Conclusion
The system already covers most core tutoring workflows. The biggest remaining gaps relative to the required upgrade path are **task routing**, **retrieval quality improvements**, **deeper image understanding**, and **specialized math handling**. Approval is required before Step 2 can be marked completed or before moving to Step 3.

## Step 3 - Architecture Design

Date: 2026-04-04
Status: Designed and awaiting approval.

### Goal
Design a modular upgrade architecture that extends the current system without breaking existing routes, sessions, quotas, or UI flows.

### Design Principles
1. **Preserve contracts first** — keep current REST/WS endpoints stable and insert new logic behind the existing service layer.
2. **Separate orchestration from execution** — routing, retrieval, ingestion, and generation should be distinct modules.
3. **Prefer additive modules** — new capabilities should plug into the current monolith before any extraction.
4. **Keep user/session context central** — all orchestration should respect the existing `user_id`, `session_id`, `content_id`, quota, and history model.

---

### Target Modular Architecture

```text
Frontend / Existing Routes
        |
        v
API Compatibility Layer (`api/routes.py`, `api/websocket.py`)
        |
        v
Task Router Layer
  - intent classification
  - task policy / entitlement checks
  - fallback rules
        |
        +-------------------+--------------------+--------------------+
        |                   |                    |                    |
        v                   v                    v                    v
Learning Executors     Retrieval Orchestrator  Ingestion Orchestrator  Utility Executors
(chat/lesson/quiz)     (multi-index RAG)       (multi-modal parsing)   (translation/math/etc.)
        |                   |                    |                    |
        v                   v                    v                    v
Current generators     Vector + lexical index   PDF/OCR/image parsers   specialized adapters
and service ports      adapters + reranker      metadata enrichment      with shared policies
```

---

### 1) Multi-Modal Ingestion Architecture

#### Proposed Components
- `modules/ingestion_orchestrator.py`
  - central entry for all new ingestion jobs
  - determines file/media type and dispatches to the right parser
- `modules/parsers/pdf_parser.py`
- `modules/parsers/image_parser.py`
- `modules/parsers/text_parser.py`
- `modules/parsers/ocr_adapter.py`
- `modules/parsers/vision_adapter.py` (future-facing for diagram/image understanding)
- `modules/metadata_enrichment.py`
  - extracts title, class, subject, chapter hints, keywords, language, and modality tags

#### Ingestion Pipeline
1. File enters via existing upload route.
2. Ingestion orchestrator detects modality:
   - PDF/document
   - image/photo/diagram
   - plain text/notes
3. Appropriate parser extracts content.
4. Metadata enrichment attaches:
   - `source_type`
   - `language`
   - `subject`
   - `chapter_hint`
   - `content_tags`
5. Output is normalized into a shared `DocumentChunk` shape:
   - `text`
   - `source`
   - `chunk_id`
   - `modality`
   - `metadata`
6. Normalized chunks are published to the retrieval layer.

#### Why this is modular
- Existing `ingestion.py` and `ocr.py` stay operational.
- The new orchestrator becomes the compatibility wrapper for future modalities without forcing route changes.

---

### 2) Multi-Index RAG Architecture

#### Problem in the current design
The current retrieval path is strong but mostly centered on one FAISS store plus filtering. That works for baseline tutoring, but it does not yet separate different knowledge scopes or support richer ranking.

#### Proposed Index Strategy
Use a retrieval orchestrator with multiple logical indexes:

1. **Curriculum Index**
   - source: `knowledge_base/`
   - purpose: syllabus and textbook grounding

2. **User Upload Index**
   - source: uploaded PDFs/images/notes
   - purpose: personal study material grounding

3. **Session Memory Index**
   - source: chat/session artifacts, recent summaries, lesson outcomes
   - purpose: short-horizon personalization and follow-up continuity

4. **Artifact Index**
   - source: flashcards, quizzes, lesson cards, assessment outputs
   - purpose: retrieve previously generated learning artifacts as context

#### Proposed Retrieval Stack
- `modules/retrieval_orchestrator.py`
- `modules/retrievers/vector_retriever.py`
- `modules/retrievers/keyword_retriever.py`
- `modules/retrievers/session_retriever.py`
- `modules/reranker.py`
- `modules/context_builder.py`

#### Retrieval Flow
1. Task router passes task + query + scope.
2. Retrieval orchestrator chooses indexes based on task:
   - chat -> curriculum + uploads + session memory
   - lesson -> curriculum + uploads + prior lesson artifacts
   - quiz -> curriculum + lesson artifacts + session memory
3. Each retriever returns candidates independently.
4. Reranker merges and scores candidates.
5. Context builder produces a bounded context packet for the selected executor.

#### Recommended Context Packet Shape
- `task`
- `query`
- `citations[]`
- `context_chunks[]`
- `confidence_score`
- `source_mix` (`curriculum`, `upload`, `session`, `artifact`)

#### Result
This keeps the current FAISS foundation but evolves it into a multi-source retrieval architecture instead of a single-path search call.

---

### 3) Task Router Architecture

#### Purpose
Add an explicit router that decides **what kind of tutoring action** a request represents before model invocation.

#### Proposed Components
- `modules/task_router.py`
- `modules/task_contracts.py`
- `modules/task_policies.py`
- `modules/task_executors/`
  - `chat_executor.py`
  - `lesson_executor.py`
  - `quiz_executor.py`
  - `flashcard_executor.py`
  - `assessment_executor.py`
  - `translation_executor.py`
  - `math_executor.py` (future dedicated path)

#### Router Responsibilities
1. classify the user request intent
2. validate entitlement / quota / role rules
3. choose the execution path
4. choose retrieval scope
5. choose the model profile or specialized executor
6. standardize the response envelope back to existing routes

#### Suggested Routing Categories
- `qa`
- `lesson`
- `quiz`
- `flashcards`
- `assessment`
- `translation`
- `math`
- `admin/system`

#### Routing Decision Inputs
- route source (`/ask`, `/ws/ask`, lesson, quiz, etc.)
- explicit frontend mode
- content context presence
- user role
- quota/plan entitlement
- lightweight intent heuristics or classifier result

#### Fallback Policy
If intent confidence is low:
- default to `qa`
- preserve current behavior
- log the ambiguous case for later tuning

---

### Integration with the Existing System

#### Preserve as-is
- `api/routes.py`
- `api/websocket.py`
- `ServiceRegistry`
- auth/session/quota layers
- lesson/quiz/flashcard generators

#### Insert behind current entry points
- `/ask` and `/ws/ask` call the task router first
- task router selects retrieval plan + executor
- executors reuse current modules (`rag.py`, `lesson_plan.py`, `quiz.py`, `flashcards.py`, `assessment.py`)

This gives modular behavior without forcing a UI or API rewrite.

---

### Recommended Phase Order
1. **Introduce task router shell** behind current chat endpoints.
2. **Introduce retrieval orchestrator** while keeping FAISS as the first index backend.
3. **Wrap ingestion in a multi-modal orchestrator** using current PDF/OCR code paths.
4. **Add specialized math executor** as a separate route through the router.
5. **Only then** consider deeper extraction or service splitting.

### Step 3 Conclusion
The recommended architecture is a **modular orchestration layer** built on top of the current monolith: a **multi-modal ingestion orchestrator**, a **multi-index retrieval orchestrator**, and a **task router** that dispatches to existing and future executors. Approval is required before Step 3 can be marked completed or before moving to Step 4.
