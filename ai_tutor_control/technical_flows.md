# Technical Flows

## Backend Startup

```mermaid
sequenceDiagram
  participant CLI as run.py
  participant App as FastAPI lifespan
  participant FAISS as faiss_store
  participant DB as SQLite
  participant Jobs as file_management
  participant KB as kb_sync

  CLI->>CLI: parse --reindex and bind config
  CLI->>CLI: probe configured port
  CLI->>App: uvicorn app.main:app
  App->>FAISS: load_index()
  App->>DB: init_db()
  DB->>DB: create tables and run migrations/seeds
  App->>Jobs: recover_indexing_jobs()
  App->>KB: schedule start_reindex_job() if enabled
```

## REST Ask Flow

```mermaid
sequenceDiagram
  participant UI as ChatPanel/useChatSendMessage
  participant API as POST /ask
  participant Auth as dependencies/auth
  participant Policy as policy
  participant Router as task_router
  participant Exec as utility/generator executors
  participant RAG as rag.generate_answer
  participant Model as model_manager
  participant DB as SQLite

  UI->>API: query, session_id, content_id, task/model
  API->>Auth: get_current_user()
  Auth-->>API: user payload
  API->>Router: route_task()
  API->>Policy: consume_quota("ask")
  alt utility or explicit generator task
    API->>Exec: execute task
  else normal QA/RAG
    API->>RAG: generate_answer()
    RAG->>DB: load history and session content
    RAG->>RAG: retrieve context and validate grounding
    RAG->>Model: generate_response()
    Model-->>RAG: answer
    RAG->>DB: save_chat()
  end
  API-->>UI: answer, session_id, route metadata
```

## WebSocket Ask Flow

```mermaid
sequenceDiagram
  participant UI as websocket.js
  participant WS as /ws/ask
  participant Auth as ws_auth
  participant Policy as policy
  participant RAG as rag.generate_answer_stream
  participant Model as model_manager

  UI->>WS: connect with chat.<token> subprotocol
  WS->>Auth: authenticate_websocket()
  Auth-->>WS: user or close 1008
  UI->>WS: JSON query payload
  WS->>Policy: consume_quota("ask")
  WS-->>UI: status Preparing your answer
  WS->>RAG: generate_answer_stream()
  RAG->>Model: generate_response_stream()
  loop tokens
    Model-->>RAG: token
    RAG-->>WS: token/metadata
    WS-->>UI: {type:"chunk", data}
  end
  WS-->>UI: {type:"end"}
```

## Retrieval and Grounding Pipeline

```mermaid
flowchart TD
  A["Query + user/session/content"] --> B["Resolve selected content ref"]
  B --> C["Load chat history and summary context"]
  C --> D["Infer retrieval task and query variants"]
  D --> E["FAISS semantic search"]
  E --> F["Hybrid rerank and dedupe"]
  F --> G{"Selected file but weak context?"}
  G -- yes --> H["Recover chunks directly from selected file"]
  G -- no --> I["Token-budget context limiting"]
  H --> I
  I --> J["Build prompt"]
  J --> K["Generate local/cloud model response"]
  K --> L{"Grounded enough?"}
  L -- no --> M["Context fallback answer"]
  L -- yes --> N["Format by query intent"]
  M --> O["Persist chat and return"]
  N --> O
```

## Upload and Indexing Flow

```mermaid
sequenceDiagram
  participant UI as ChatPanel
  participant API as /files/upload
  participant FM as file_management
  participant DB as SQLite
  participant Worker as ThreadPoolExecutor
  participant Ingest as ingestion/ocr
  participant FAISS as faiss_store

  UI->>API: multipart file + class/subject/folder/display
  API->>FM: upload_file()
  FM->>FM: validate names and file type
  FM->>FM: save under app/uploads/user_hash/...
  FM->>DB: uploaded_files + file_index_status + indexing_jobs
  FM->>Worker: submit indexing job
  Worker->>Ingest: ingest_pdf() or ingest_image()
  Ingest->>FAISS: add_doc()
  FAISS->>FAISS: save index/metadata
  Worker->>DB: mark indexed or failed
  UI->>API: poll /files/index-status
```

## Knowledge Base Tree and PDF Viewer

```mermaid
flowchart LR
  A["useKnowledgeBaseLoader"] --> B["GET /classes"]
  B --> C["GET /subjects?class_name"]
  C --> D["GET /folders?class_name&subject"]
  D --> E["GET /contents?..."]
  E --> F["Content refs kb:<encoded path>"]
  F --> G["ChatPanel selectedContent"]
  G --> H["GET /pdf?content_id=..."]
  H --> I["FileResponse PDF in viewer"]
```

## Lesson Plan Flow

```mermaid
sequenceDiagram
  participant UI as LessonPanel
  participant API as routes.py
  participant Lesson as lesson_plan
  participant RAG as retrieve_chunks
  participant Model as model_manager
  participant DB as SQLite

  UI->>API: POST /lesson-plan/create
  API->>Lesson: generate_lesson_plan()
  Lesson->>RAG: retrieve_chunks(chapter, filter_path)
  Lesson->>Model: generate_response(task=lesson)
  Lesson->>Lesson: parse/normalize/fallback/rewrite steps
  Lesson->>DB: save lesson_plans and lesson_cards
  API-->>UI: plan
  UI->>API: GET /lesson-plan/{id}/cards
  UI->>API: POST complete card
```

## Quiz and Flashcard Artifact Flow

```mermaid
flowchart TD
  A["Lesson card or selected content"] --> B{"Artifact type"}
  B --> C["QuizPanel: /cards/{card_id}/quiz/generate or /quiz/generate"]
  B --> D["FlashcardPanel: /cards/{card_id}/flashcards/generate or /flashcards/"]
  C --> E["quiz.py or artifacts.py"]
  D --> F["flashcards.py or artifacts.py"]
  E --> G["retrieve context + model JSON + normalize"]
  F --> H["extract/retrieve text + model cards + normalize"]
  G --> I["Persist quiz/artifact"]
  H --> I
  I --> J["Latest/list/session APIs"]
```

## Auth and Session Lifecycle

```mermaid
sequenceDiagram
  participant Login as Login.jsx
  participant API as /login
  participant Auth as auth/user_manager
  participant App as App.jsx
  participant Store as localStorage + cookie

  Login->>API: email/password
  API->>Auth: authenticate_user()
  Auth-->>API: user
  API-->>Login: token + user, Set-Cookie
  Login->>Store: store token/user/session ids
  Login->>App: handleLogin()
  App->>API: GET /auth/session on bootstrap
  API-->>App: current user or 401
  App->>Store: clear state on session:expired/logout
```

## Async and Background Work

- Startup KB reindex is scheduled from FastAPI lifespan as a background task/threaded job.
- Upload indexing uses an in-process `ThreadPoolExecutor` and DB-backed job rows for recovery.
- WebSocket streaming wraps synchronous generators with `asyncio.to_thread` per token.
- Offline frontend mutations queue in localStorage and replay on browser `online`.
- No external durable queue system is present.
