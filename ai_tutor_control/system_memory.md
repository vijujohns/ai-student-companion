# System Memory

## High-Level Summary

This repository contains an AI student companion under `v3`: a FastAPI backend and Vite/React frontend for textbook-grounded tutoring. It supports authenticated chat, RAG over bundled/uploaded educational PDFs, lesson plans, quizzes, flashcards, notes, assessments, progress analytics, subscriptions, role-based collaboration, and admin model/reindex controls.

The system is a modular monolith. The backend uses SQLite for application data, FAISS for vector search, local GGUF models via llama-cpp with optional OpenAI/Groq-compatible cloud models, and in-process background indexing. The frontend is a browser SPA/PWA with React local state, localStorage session/context/offline queues, and WebSocket streaming for chat.

## Key Responsibilities

- `v3/backend/run.py`: backend process launcher and optional startup reindex flag.
- `app/main.py`: FastAPI app, startup, CORS, error envelopes.
- `app/api/routes.py`: primary REST contract.
- `app/api/websocket.py`: streaming ask/lesson/quiz endpoints.
- `modules/db.py`: SQLite schema/migrations/seeds.
- `modules/auth.py`, `user_manager.py`, `dependencies.py`, `ws_auth.py`: identity, JWT, cookies, roles, guards.
- `modules/rag.py`: retrieve -> generate -> validate -> format -> save chat.
- `modules/model_manager.py`: model profiles, local/cloud model selection, prompt/generation.
- `modules/faiss_store.py`, `retrieval_orchestrator.py`, `ingestion.py`, `file_management.py`, `kb_sync.py`: document ingestion, vector search, uploads, indexing.
- `modules/lesson_plan.py`, `quiz.py`, `flashcards.py`, `artifacts.py`, `assessment.py`, `notes.py`: learning features.
- `modules/analytics.py`, `policy.py`, `subscriptions.py`, `adapters/default_services.py`: progress, quota, commerce, relationships, application services.
- `frontend/src/App.jsx`: auth bootstrap and shell.
- `frontend/src/components/ChatPanel.jsx`: main workspace and orchestration hub.
- `frontend/src/services/api.js`: HTTP wrapper, auth injection, offline queue/cache.
- `frontend/src/services/websocket.js`: streaming socket manager.

## Important Flows

- Startup: `run.py` -> `app.main` lifespan -> `load_index` -> `init_db` -> recover indexing jobs -> optional KB reindex.
- Chat REST: `/ask` -> auth -> quota -> task_router -> utility/generator or `rag.generate_answer`.
- Chat streaming: `websocket.js` -> `/ws/ask` -> ws auth -> quota -> task routing -> `generate_answer_stream` -> chunks/end.
- Retrieval: resolve session/content -> history -> FAISS search/query variants -> selected-file recovery -> prompt -> model -> grounding fallback -> formatter.
- Upload: `/files/upload` -> validate/store upload -> DB job rows -> thread pool -> ingest PDF/image/OCR -> FAISS save -> status polling.
- Lesson: `/lesson-plan/create` -> retrieve chunks -> model plan -> parse/fallback/rewrite -> save plan/cards -> card completion/artifacts.
- Quiz/flashcards: selected content/card -> retrieve/extract context -> model JSON/cards -> normalize -> persist -> latest/session APIs.
- Progress/collab: activity/assessment/assignments feed analytics; mentors link students and view/update notes/assignments.

## Known Issues and Constraints

- Several large files are architectural pressure points: `routes.py`, `rag.py`, `model_manager.py`, `lesson_plan.py`, `analytics.py`, `ChatPanel.jsx`, `RoleHubPanel.jsx`.
- SQLite, in-process FAISS state, and in-process job queues limit production scalability.
- Auth uses both HttpOnly cookie and localStorage bearer token; localStorage token is a security concern.
- WebSocket auth token is passed via subprotocol.
- Password reset by email + DOB is not production-grade.
- API envelope consistency is partial.
- Offline mutation queue lacks conflict resolution.
- Upload/indexing lacks durable external queue and production scanning.
- Some source strings show encoding corruption from Windows console/emoji output.
- Existing worktree had pre-existing modifications/deletions before this analysis, including `v3/frontend/src/components/ChatPanel.jsx`.

## Architecture Decisions

- Use `configs/settings.json` for network, model, task, profile, and RAG settings.
- Use email as username for newly registered users, while preserving legacy username fallback.
- Use content references rather than raw paths:
  - KB refs point to encoded knowledge-base paths.
  - Upload refs point to uploaded file ids.
- Disable RAG cache in development/test-like environments.
- Keep startup KB reindex disabled unless explicitly requested.
- Use service ports/facade for some seams, but migration is incomplete.

## Naming and Conventions

- Backend module names are snake_case under `app/modules`.
- Request schemas live in `schemas/request.py`; response schemas in `schemas/response.py`.
- REST route groups are plain paths without `/api/v1`.
- User id is usually `username`; for new users this is the email.
- Session ids are UUID-like strings managed by frontend/localStorage and persisted on chat/lesson/quiz/flashcard data.
- Model profile keys include `balanced`, `best-quality`, `fastest`, `single-model`, `safe-fallback`, `groq-cloud`.
- Plan/quota actions include at least `ask` and feature-specific generation actions.

## Important Assumptions

- `v3` is the active app; root files mostly start it.
- Documentation files may be outdated and should not be trusted without source validation.
- PDF bodies are application data, not code; class/subject/folder structure matters for UX and metadata.
- Redis is optional because `cache.py` has in-memory fallback.
- Local model files may or may not exist under `v3/backend/models`; model availability logic chooses fallbacks.
- Tesseract may be absent; OCR paths must degrade gracefully.

## Future Task Guidance

- For API changes, inspect `routes.py`, request/response schemas, frontend `apiFetch` callers, and relevant tests.
- For chat/RAG changes, inspect `rag.py`, `model_manager.py`, `faiss_store.py`, `retrieval_orchestrator.py`, `answer_formatter.py`, and stream token utilities.
- For upload/index changes, inspect `file_management.py`, `ingestion.py`, `ocr.py`, `kb_sync.py`, and frontend upload/status code in `ChatPanel`.
- For UI changes, start with the target panel but check `ChatPanel` for orchestration/state.
- For role/collaboration changes, inspect `RoleHubPanel`, `default_services.py`, relationship routes, and `analytics.py`.
- Always check tests under both `v3/test_suite/backend` and `v3/test_suite/frontend` for the affected feature.
