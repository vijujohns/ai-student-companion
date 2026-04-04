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
