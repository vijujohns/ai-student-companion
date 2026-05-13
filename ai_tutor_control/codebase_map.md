# Codebase Map

Generated from source inspection on 2026-05-03. Existing documentation files were intentionally ignored.

## Repository Shape

- Root operational scripts: `start-dev.ps1`, `start-dev.bat`, `start-app.bat`.
- Active app: `v3/`.
- Backend: `v3/backend`, Python FastAPI application.
- Frontend: `v3/frontend`, Vite + React single page app.
- Shared runtime config: `v3/configs/settings.json`.
- Persistent data: `v3/data` with SQLite DB, FAISS index, metadata, precomputed PDF summaries.
- Knowledge base: `v3/knowledge_base`, 92 PDF textbooks organized by class/subject/folder.
- User uploads: `v3/app/uploads`, email-hash scoped upload storage.
- Tests: `v3/test_suite/backend` and `v3/test_suite/frontend`.

Generated/ignored implementation artifacts observed but not treated as source: `.git`, `.venv`, `__pycache__`, `dist`, logs, `.coverage`, Playwright test output, PDF content bodies.

## Entry Points

### Backend

- `v3/backend/run.py`
  - Normalizes Windows console output.
  - Reads backend bind host/port from config.
  - Accepts `--reindex` to set startup indexing mode.
  - Avoids starting a duplicate backend if the configured port already serves `/openapi.json`.
  - Launches `uvicorn app.main:app`.

- `v3/backend/app/main.py`
  - Creates FastAPI app named `AI Tutor`.
  - On lifespan startup:
    - loads FAISS index;
    - initializes/migrates SQLite DB;
    - recovers queued/running upload indexing jobs unless disabled/test;
    - optionally schedules KB reindex based on `KB_REINDEX_MODE`.
  - Installs CORS from `configs/settings.json`.
  - Registers REST router and WebSocket router.
  - Provides uniform exception envelopes using `message_catalog`.

### Frontend

- `v3/frontend/src/main.jsx`
  - Registers PWA service worker.
  - Renders `App` inside `AppErrorBoundary`.

- `v3/frontend/src/App.jsx`
  - Handles auth bootstrap, online/offline state, PWA install prompt, backend health probe, density setting, shell navigation.
  - Shows `Login` when no valid session exists.
  - Shows `ChatPanel` workspace after login.

## Backend Module Topology

### API Layer

- `app/api/routes.py`
  - Main REST router.
  - Endpoints cover auth, chat, sessions, context, files, knowledge base tree, PDF serving, lessons, quizzes, flashcards, artifacts, assessments, progress, subscriptions, language/preferences, role collaboration, and admin model/reindex operations.
  - Delegates large seams to `ServiceRegistry` plus feature modules.

- `app/api/websocket.py`
  - WebSocket endpoints:
    - `/ws`: authenticated basic streaming.
    - `/ws/ask`: main streaming RAG/task endpoint.
    - `/ws/lesson`: lesson step streaming.
    - `/ws/quiz`: quiz question/feedback streaming.
  - Authenticates via token subprotocol/cookie/header helpers.

### Core

- `core/config_loader.py`: loads `configs/settings.json`, environment overrides, app env, network, CORS, Redis, model and RAG config.
- `core/debug_logger.py`: gated debug logging helpers using `DEBUG_LOGGING`.
- `core/security.py`: thin compatibility wrapper over auth token creation/verification.

### Persistence and Identity

- `modules/db.py`: SQLite connection helper, table creation, migrations, message/subscription seeding.
- `modules/user_manager.py`: PBKDF2 password hashing, default users, register/reset/profile update.
- `modules/auth.py`: JWT create/verify, login authentication, HttpOnly cookie helpers.
- `modules/dependencies.py`: FastAPI auth dependency, role guard, quota guard, session ownership guard.
- `modules/ws_auth.py`: WebSocket token extraction and authentication.

### Learning and AI

- `modules/rag.py`: main retrieve-generate-validate-format pipeline.
- `modules/model_manager.py`: local/cloud model selection, profile selection, prompt building, generation and streaming.
- `modules/faiss_store.py`: embedding model, FAISS index, metadata persistence, semantic search.
- `modules/retrieval_orchestrator.py`: query/index planning, lexical and hybrid reranking, context packet building.
- `modules/answer_formatter.py`: deterministic answer cleanup and intent-aware formatting.
- `modules/query_classifier.py`: regex-based query intent classification.
- `modules/task_router.py`: maps explicit or inferred tasks to executors/model tasks.
- `modules/generator_executor.py`: summary/quiz/flashcard generation from selected content.
- `modules/utility_executor.py`: math/translation/explorer utility dispatch.
- `modules/math_executor.py`: safe-ish math expression normalization and solution formatting.
- `modules/translation.py` and `translation_executor.py`: language list/detection/translation task handling.

### Knowledge and Ingestion

- `modules/ingestion.py`: PDF/image extraction, OCR fallback, chunking, metadata, summaries, FAISS document ingestion.
- `modules/ocr.py`: Tesseract/Pillow availability checks and OCR extraction.
- `modules/file_management.py`: upload validation, user storage roots, content references, indexing job queue/recovery/status/tree.
- `modules/kb_sync.py`: admin/startup reindex orchestration for knowledge-base PDFs.

### Learning Features

- `modules/history.py`: chat persistence by user/session.
- `modules/lesson_plan.py`: lesson plan creation, cards, progress, next-step behavior.
- `modules/quiz.py`: quiz generation, persistence, latest/list/rename/delete/submit.
- `modules/flashcards.py`: flashcard generation route and artifact persistence support.
- `modules/artifacts.py`: card quiz/flashcard artifacts and flashcard session APIs.
- `modules/notes.py`: saved summary notes CRUD.
- `modules/assessment.py`: subject quiz and question paper generation/persistence/attempts.

### Product, Progress, Collaboration

- `modules/policy.py`: plan defaults, quota checking/consumption/release.
- `modules/subscriptions.py`: class rates, promotions, entitlement lookup, quote, activation.
- `modules/analytics.py`: activity log, mastery, dashboards, insights, study plan, assignment-derived history.
- `modules/progress.py`: legacy/simple lesson progress helpers.
- `modules/messages.py`: message catalog lookup and API envelope helper.
- `modules/adapters/default_services.py`: application-service facade implementing identity, relationships, progress, knowledge, commercial, and learning-session ports.
- `modules/interfaces/service_ports.py`: Protocol definitions for those seams.

## Frontend Module Topology

### Shell and Services

- `App.jsx`: application shell and auth lifecycle.
- `services/api.js`: API base URL resolution, bearer-token injection, cookie credentials, 401 session-expiry event, offline GET cache and mutation queue.
- `services/websocket.js`: multi-socket manager for `ask`, `lesson`, `quiz`, auth subprotocol token, runtime close hints.
- `services/pwa.js`: service worker registration and install prompt wiring.
- `public/sw.js`: static service worker for app shell/static caching.

### Workspace Components

- `ChatPanel.jsx`: central workspace controller for chat, knowledge selection, uploads, viewer, billing, notes sidebar, admin reindex, panel navigation, WebSocket send/stream handling.
- `LessonPanel.jsx`: lesson plan and lesson-card workflow.
- `QuizPanel.jsx`: quiz generation/submission workflow.
- `FlashcardPanel.jsx`: flashcard generation, latest artifact loading, save state.
- `AssessmentPanel.jsx`: subject quiz/question paper generation and attempt recording.
- `ProgressPanel.jsx`: student dashboard, insights, study plan, reminders, assignment actions.
- `RoleHubPanel.jsx`: student/mentor/admin hub for relationships, assignments, notes, model profile admin, reports.
- `AssignmentsPanel.jsx`: assignment list/filter/status update for students.
- `NotesPanel.jsx`: rich-ish markdown note editor and saved notes CRUD.
- `SummaryViewer.jsx`: structured summary parser/viewer and save-to-notes entry.
- `ProfilePanel.jsx`: profile display/edit.
- `BillingPanel.jsx`: current plan/catalog/quote/activation display support.
- `AdminPanel.jsx`: admin model profile switcher.
- `LanguagePicker.jsx`: preferred language dropdown.
- `Login.jsx`: login/register/reset UI.
- `VoiceControl.jsx`: Web Speech input.
- `MessageContent.jsx`: Markdown rendering.
- `AppErrorBoundary.jsx`: React error boundary.

### Hooks

- `useChatSendMessage`: sends chat messages via WebSocket and persists session content.
- `useChatWebSocketLifecycle`: connects/disconnects ask WebSocket.
- `useChatScroll`: bottom/near-bottom scroll handling.
- `usePlanSummary`: loads plan and usage limits.
- `useScopedSessionActions`: rename/delete sessions across chat/lesson/quiz/flashcards.
- `useSessionLoaders`: loads chat, lesson, quiz, and flashcard session lists.
- `useKnowledgeBaseLoader`: loads classes/subjects/folders/contents/uploaded file tree.
- `useKnowledgeBaseSelectionHandlers`: manages cascading class/subject/folder/content selection.
- `useStreamTimers`: tracks streaming elapsed/stalled timers.
- `useChatComposerLayout`: measures composer layout.
- `useViewerLayout`: split-view PDF/layout resizing.

### Utilities

- `chatPanelSelectors.js`: usage limit state and context-filtered sessions.
- `contentCatalog.js`: merges KB and upload trees into selectable content.
- `kbSelectors.js`: pending upload count and KB status text.
- `sessionCrud.js`: shared rename/delete API behavior.
- `speech.js`: browser speech synthesis helper.
- `streamToken.js`: stream payload normalization, quick replies, completion rules.

## APIs

Major REST groups:

- Health: `GET /health/runtime`.
- Auth/profile: `POST /login`, `POST /logout`, `GET /auth/session`, `POST /register`, `POST /reset-password`, `GET/PUT /profile`.
- Chat/session/context: `POST /ask`, `GET /history`, `GET /sessions`, `PUT/DELETE /sessions/{id}`, `GET/PUT /sessions/{id}/content`, `GET/POST /context`.
- Knowledge/files: `POST /files/upload`, `GET /files/tree`, `GET /files/index-status`, `POST /files/reindex`, `GET /pdf`, `GET /classes`, `GET /subjects`, `GET /folders`, `GET /contents`, `GET /ocr/status`.
- Admin indexing/model: `POST /admin/reindex*`, `GET /admin/reindex-status`, `GET /admin/reindex/status/{job_id}`, `GET/PUT /admin/model-profiles`.
- Lessons/artifacts: `POST /lesson-plan/create`, `GET /lesson-plan`, `GET/PUT/DELETE /lesson-plan/sessions`, `GET /lesson-plan/next`, `POST /lesson-plan/progress`, `GET /lesson-plan/{id}/cards`, `POST /lesson-plan/{id}/cards/{card_id}/complete`, `GET/POST /artifacts`.
- Quiz/flashcards: `POST /quiz/generate`, `GET /quiz/sessions`, `GET /quiz/latest`, `GET /quiz/{id}`, `POST /quiz/{id}/submit`, `GET /flashcards/sessions`, `GET /flashcards/latest`, flashcard router mounted under `/flashcards/`, card artifact generation routes.
- Assessment: `POST /assessment/subject-quiz`, `POST /assessment/question-paper`, `GET /assessment/papers`, `GET /assessment/papers/{id}`, `POST /assessment/papers/{id}/attempt`.
- Progress/preferences/language: `GET /progress/*`, `POST /progress/activity`, `GET /languages`, `POST /translate`, `GET/PUT /preferences`.
- Subscriptions: `GET /plan/me`, `GET /plan/limits`, `GET /subscription/catalog`, `POST /subscription/quote`, `POST /subscription/activate`.
- Relationships/collaboration: `POST /relationships/link-student`, `GET /relationships/my-students`, `GET /relationships/my-mentors`, student progress/notes/assignments CRUD.

WebSocket groups:

- `/ws/ask`: primary streaming answer path.
- `/ws/lesson`: step loop for lesson sessions.
- `/ws/quiz`: sequential question/feedback loop.

## Data Stores

- SQLite: `v3/data/app.db`.
  - Core tables include users, chat history, lesson plans/progress/quizzes/results, usage counters, message catalog, uploads/index jobs/file status, lesson cards/card progress/artifacts, profile audit, subscriptions/promotions/entitlements, assessment papers, learning time log, mastery scores, preferences, app settings, relationships, collaboration notes, mentor assignments, study plan progress/snapshots.
- FAISS and metadata: `faiss.index`, `documents.pkl`, `metadata.json`, `logical_indexes.json`.
- Precomputed summaries: `pdf_summaries.json`.
- Uploaded files: `v3/app/uploads/<email_hash>/<class>/<subject>/<folder>/<file>`.
- Browser localStorage: auth token, session ids, role/user, learning context, offline queue/cache, UI density, role-hub templates.

## State Management Patterns

- Backend state is mostly SQLite plus module-level caches/locks:
  - LLM cache and per-model locks in `model_manager`.
  - FAISS documents/index metadata in `faiss_store`.
  - Redis client/circuit breaker or in-memory fallback in `cache`.
  - In-process thread pool for file indexing.
- Frontend state is local React `useState`/`useEffect`; no Redux/router.
- Session ids are stored in localStorage and passed explicitly to APIs/WebSockets.
- Auth uses both localStorage bearer token and HttpOnly cookie; API wrapper sends bearer when present and always uses credentials.

## External Integrations

- FastAPI/Uvicorn.
- SQLite.
- Redis optional cache, with in-memory fallback.
- FAISS CPU.
- Sentence Transformers embedding model, default `BAAI/bge-base-en-v1.5`.
- llama-cpp-python local GGUF models.
- OpenAI-compatible cloud providers: OpenAI and Groq via config/env keys.
- pypdf and python-docx for extraction support; Tesseract/Pillow for OCR.
- deep-translator and optional IndicTrans2 translation path.
- React, Vite, React Icons, React Markdown, react-datepicker.
- Playwright and Vitest test tooling.
