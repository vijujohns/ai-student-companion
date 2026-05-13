# Module Analysis: Backend API

## `app/main.py`

- Purpose: FastAPI composition root.
- Inputs: process environment, `configs/settings.json`, HTTP requests, app startup.
- Outputs: configured `app`, JSON exception envelopes, CORS behavior, background startup indexing.
- Internal logic:
  - Loads FAISS index before DB init.
  - Initializes DB schema and seeds data via `init_db`.
  - Recovers upload indexing jobs except in test or when disabled.
  - Defers startup KB reindex unless explicitly enabled.
  - Wraps HTTP/validation/unhandled errors in message catalog envelopes.
- Dependencies:
  - Internal: routes, websocket, FAISS, KB sync, file management, DB, config loader, messages.
  - External: FastAPI, Starlette middleware, dotenv.
- Interactions:
  - Centralizes startup ordering for persistence and retrieval.
  - Makes `/health/runtime` meaningful to frontend diagnostics and WebSocket close hints.
- Risks/tech debt:
  - Startup work is synchronous-heavy and can delay availability.
  - Encoded console strings appear corrupted in several files, suggesting Windows encoding churn.
  - Startup loads FAISS before DB init; if future index metadata depends on migrations, ordering may matter.
- Tests:
  - Covered indirectly by backend API/e2e/contract tests.

## `app/api/routes.py`

- Purpose: Main REST API surface.
- Inputs: Pydantic request schemas, JWT/current user, form uploads, query/path params.
- Outputs: JSON envelopes or raw dictionaries, file responses, DB mutations, background jobs.
- Internal logic:
  - Uses helper guards for quota, reminder settings, session ownership, and progress logging.
  - Routes `/ask` through `task_router`; uses utility/generator executors for explicit tasks and `rag.generate_answer` for normal QA.
  - Uses `ServiceRegistry` for identity, relationships, progress, knowledge, commercial, and session operations.
  - Directly wires feature modules for lessons, quizzes, artifacts, assessments, preferences, translation, admin model profile, indexing.
- Dependencies:
  - Internal: almost every backend feature module plus request/response schemas.
  - External: FastAPI, FileResponse.
- Interactions:
  - Frontend panels mostly call this file via `services/api.js`.
  - `routes.py` is the contract hub between UI and domain modules.
- Risks/tech debt:
  - Very large file with mixed controller, policy, service orchestration, and response shaping.
  - Some routes use service facade, others call modules directly; pattern is inconsistent.
  - Duplicated upload endpoints (`/files/upload` and `/upload/file`) need contract clarity.
  - `flashcards_router` is included inside this router while most routes are declared inline.
- Tests:
  - Broad backend tests: auth, contracts, file management, lesson, quiz, assessment, progress, subscriptions, roles, schemas, e2e.

## `app/api/websocket.py`

- Purpose: Authenticated streaming transport.
- Inputs: WebSocket connection, JWT from subprotocol/cookie, JSON text messages.
- Outputs: JSON text frames with `type=status|chunk|error|end|lesson_step|feedback|...`.
- Internal logic:
  - Authenticates before `accept`.
  - `/ws/ask` parses payload, consumes ask quota, routes task, streams sync generators through `asyncio.to_thread`, sends keepalive status notices.
  - `/ws/lesson` loads next lesson steps and waits for client completion events.
  - `/ws/quiz` streams quiz questions and records answers one by one.
- Dependencies:
  - Internal: RAG, lesson plan, quiz, ws auth, policy, messages, task router, executors, debug logger.
  - External: FastAPI WebSocket, asyncio.
- Interactions:
  - `frontend/src/services/websocket.js` connects using `chat.<token>` subprotocol.
  - `ChatPanel` sends ask messages; lesson/quiz sockets are available but much of the current UI uses REST for generation.
- Risks/tech debt:
  - Long-lived LLM calls still consume in-process resources; no backpressure or cancellation propagation beyond socket close.
  - Quota release happens on streaming exception but not on client disconnect after partial activity.
  - Message frame schema is informal and partially mixed (`data` can be string or structured token).
- Tests:
  - `test_websocket.py`, `test_websocket_routes.py`, frontend WebSocket/session expiry e2e/unit tests.
