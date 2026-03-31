# React ↔ FastAPI Contract Bridge

## Purpose
Exact request/response contract between the React frontend and the FastAPI backend.
Every HTTP endpoint and WebSocket message is listed with:
- Frontend caller (file + function)
- Transport & auth requirements
- Request shape (body / form / query params)
- Success response shape (all responses wrapped by `envelope()`)
- Error codes

## Envelope Wrapper
**All** HTTP responses are wrapped by `envelope()` in `modules/messages.py`.
The payload fields are spread at the top level alongside a `message` meta-object:

```json
{
  "field1": "...",
  "field2": "...",
  "message": {
    "message_id": "MSG-1000",
    "level": "INFO",
    "user_text": "Operation completed successfully."
  }
}
```

## Auth Mechanism
- HTTP: **HTTP-only JWT cookie** (`access_token`). Set by `/login`, cleared by `/logout`.  
  Backend dependency: `get_current_user` → `require_quota` → `require_role`.
- WebSocket: JWT sent as **Sec-WebSocket-Protocol** subprotocol header.  
  Backend: `ws_auth.authenticate_websocket`.

---

## 1. Auth Endpoints

| # | Method | Path | Auth | Frontend Caller | Request Body | Success Response Fields | Error Codes |
|---|---|---|---|---|---|---|---|
| 1 | `POST` | `/login` | None | `Login.jsx::handleLogin` | `{ email: str, password: str }` | `access_token, token_type, role, username, email` | `401` invalid creds, `422` validation |
| 2 | `POST` | `/register` | None | `Login.jsx::handleRegister` | `{ first_name, last_name, email, dob (YYYY-MM-DD), password (min 6) }` | `status: "registered", email` | `409` email already exists, `422` validation |
| 3 | `POST` | `/logout` | Cookie | `App.jsx` or nav handler | _(empty)_ | `status: "logged_out"` | — |
| 4 | `GET` | `/auth/session` | Cookie | `App.jsx` bootstrap | _(none)_ | `authenticated: true, username, email, role` | `401` missing/expired cookie |
| 5 | `PUT` | `/profile` | Cookie | _(profile UI)_ | `{ first_name?, last_name?, dob?, email? }` | `profile: {...}, status: "updated"` | `400` validation, `401` |
| 6 | `POST` | `/reset-password` | None | `Login.jsx` reset form | `{ email, dob (YYYY-MM-DD), new_password (min 6) }` | `status: "password_reset"` | `400` email/DOB mismatch, `422` |

---

## 2. Chat / Ask

| # | Method | Path | Auth | Frontend Caller | Request Body | Success Response Fields | Error Codes |
|---|---|---|---|---|---|---|---|
| 7 | `POST` | `/ask` | Cookie + quota | _(legacy HTTP ask; not used in streaming UI)_ | `{ query: str (max 5000), session_id?: str, model_name?: str }` | `answer, session_id, model_used` | `401`, `429` quota, `422` |
| 8 | `GET` | `/history` | Cookie | `useSessionLoaders` | Query: `session_id=<uuid>` | `history: [{role, content, timestamp}]` | `401`, `403` ownership |

---

## 3. Sessions (Chat)

| # | Method | Path | Auth | Frontend Caller | Request / Params | Success Response Fields | Error Codes |
|---|---|---|---|---|---|---|---|
| 9 | `GET` | `/sessions` | Cookie | `useSessionLoaders` | _(none)_ | `sessions: [{id, title, last_updated, selected_content}]` | `401` |
| 10 | `DELETE` | `/sessions/{session_id}` | Cookie + ownership | `ChatPanel` / `useScopedSessionActions` | Path: `session_id` | `status: "deleted"` | `401`, `403` ownership |
| 11 | `PUT` | `/sessions/{session_id}` | Cookie + ownership | `ChatPanel` rename handler | Body: `{ title: str (max 200) }` | `status: "updated"` | `401`, `403`, `404` |
| 12 | `GET` | `/sessions/{session_id}/content` | Cookie | `useSessionLoaders` | Path: `session_id` | `session_content: str\|null` | `401`, `403` ownership |
| 13 | `PUT` | `/sessions/{session_id}/content` | Cookie | `useChatSendMessage` | Body: `{ content_id?: str, path?: str }` (one required) | `status: "updated", session_content: str\|null` | `400` neither field, `401`, `403` |

---

## 4. File Management

| # | Method | Path | Auth | Frontend Caller | Request | Success Response Fields | Error Codes |
|---|---|---|---|---|---|---|---|
| 14 | `POST` | `/files/upload` | Cookie + quota | `ChatPanel::handleUploadFile` | Multipart form: `class_name, subject_name, folder_name, display_name, upload (PDF)` | `file_id, content_id, display_name, status` | `400` bad file/path, `401`, `429` quota |
| 15 | `GET` | `/files/tree` | Cookie | upload/browse UI | _(none)_ | `items: [{file_id, display_name, content_id, indexed, ...}]` | `401` |
| 16 | `GET` | `/files/index-status` | Cookie | upload UI | Query: `file_id?=int` | `items: [{file_id, status, indexed_at, ...}]` | `401` |
| 17 | `POST` | `/files/reindex` | Cookie | admin UI | Form: `scope ("changed"\|"all"), file_id?` | `status, queued_count` | `401` |
| 18 | `GET` | `/pdf` | Cookie | PDF viewer component | Query: `content_id=<ref>` or `path=<ref>` | Binary PDF stream (`application/pdf`) | `400` no ref, `403` access denied, `404` not found |

---

## 5. Knowledge Base Browsing

All endpoints require cookie auth and return lists from `knowledge_base/` filesystem.

| # | Method | Path | Frontend Caller | Query Params | Success Response Fields | Error Codes |
|---|---|---|---|---|---|---|
| 19 | `GET` | `/classes` | upload/browse UI | _(none)_ | `classes: [str]` | `401` |
| 20 | `GET` | `/subjects` | upload/browse UI | `class_name=<str>` | `subjects: [str]` | `401`, `400` bad path |
| 21 | `GET` | `/folders` | upload/browse UI | `class_name=<str>&subject=<str>` | `folders: [str]` | `401`, `400` |
| 22 | `GET` | `/contents` | upload/browse UI | `class_name=<str>&subject=<str>&folder=<str>` | `contents: [{title, content_id}]` | `401`, `400` |

---

## 6. Lesson Plan

| # | Method | Path | Auth | Frontend Caller | Request | Success Response Fields | Error Codes |
|---|---|---|---|---|---|---|---|
| 23 | `POST` | `/lesson-plan/create` | Cookie + quota | `LessonPanel::handleGeneratePlan` | Body: `{ chapter: str (max 500), session_id?: str, lesson_context?: str (max 1000) }` | `plan_id, session_id, cards: [{id, title, summary, steps}]` | `400/422` validation, `401`, `429` quota |
| 24 | `GET` | `/lesson-plan/sessions` | Cookie | `useSessionLoaders` | _(none)_ | `sessions: [{session_id, title, last_updated}]` | `401` |
| 25 | `PUT` | `/lesson-plan/sessions/{session_id}` | Cookie | `useScopedSessionActions` | Body: `{ title: str }` | `status: "updated"` | `401`, `404` |
| 26 | `DELETE` | `/lesson-plan/sessions/{session_id}` | Cookie | `useScopedSessionActions` | Path: `session_id` | `status: "deleted"` | `401` |
| 27 | `GET` | `/lesson-plan` | Cookie | `LessonPanel` load | Query: `session_id=<uuid>` | `plan_id, session_id, title, cards: [...]` | `401` |
| 28 | `POST` | `/lesson-plan/progress` | Cookie | `LessonPanel` step progress | Body: `{ session_id, step_id: int, status: str }` | `status: "updated"` | `401`, `422` |
| 29 | `GET` | `/lesson-plan/next` | Cookie | WS lesson step fallback | Query: `session_id=<uuid>` | `next_step: {id, title, content}` or `{message: "Lesson completed"}` | `401` |
| 30 | `GET` | `/lesson-plan/{lesson_plan_id}/cards` | Cookie | `LessonPanel` card list | Path: `lesson_plan_id` | `lesson_plan_id, cards: [{id, title, summary, order, completed}]` | `401`, `404` cards not found |
| 31 | `POST` | `/lesson-plan/{lesson_plan_id}/cards/{card_id}/complete` | Cookie | `LessonPanel::handleCompleteCard` | Path: `lesson_plan_id, card_id` | `status: "completed", card_id` | `401`, `404` card not found |

---

## 7. Quiz

| # | Method | Path | Auth | Frontend Caller | Request | Success Response Fields | Error Codes |
|---|---|---|---|---|---|---|---|
| 32 | `POST` | `/quiz/generate` | Cookie + quota | `QuizPanel::handleGenerateQuiz` | Body: `{ session_id, chapter: str (max 500), quiz_context?: str (max 1000) }` | `quiz_id, quiz: [{id, question, options: [str]}]` | `401`, `422`, `429` quota |
| 33 | `GET` | `/quiz/sessions` | Cookie | `useSessionLoaders` | _(none)_ | `sessions: [{session_id, title, last_updated}]` | `401` |
| 34 | `PUT` | `/quiz/sessions/{session_id}` | Cookie | `useScopedSessionActions` | Body: `{ title: str }` | `status: "updated"` | `401`, `404` |
| 35 | `DELETE` | `/quiz/sessions/{session_id}` | Cookie | `useScopedSessionActions` | Path: `session_id` | `status: "deleted"` | `401` |
| 36 | `GET` | `/quiz/latest` | Cookie | `QuizPanel` load | Query: `session_id=<uuid>` | `quiz_id, quiz: [...]` | `401` |
| 37 | `GET` | `/quiz/{quiz_id}` | Cookie | `QuizPanel` | Query: `session_id=<uuid>` | `quiz_id, quiz: [{id, question, options}]` | `401` |
| 38 | `POST` | `/quiz/{quiz_id}/submit` | Cookie | `QuizPanel::handleSubmitQuiz` | Body: `{ session_id, answers: { q_id: selected_option } }` | `{ q_id: {correct: bool, correct_option: str} }` (result map) | `401`, `422` |
| 39 | `POST` | `/cards/{card_id}/quiz/generate` | Cookie + quota | `LessonPanel` card quiz | Path: `card_id`; Body (optional): `{ context?: str }` | `artifact_id, quiz_id, quiz: [...]` | `401`, `404` card not found, `429` |

---

## 8. Flashcards

| # | Method | Path | Auth | Frontend Caller | Request | Success Response Fields | Error Codes |
|---|---|---|---|---|---|---|---|
| 40 | `POST` | `/flashcards/` | Cookie + quota | `FlashcardPanel::handleGenerateFlashcards` (legacy KB mode) | Body: `{ class_name, subject, content_type, chapter?, num_cards?: int, session_id? }` | `flashcards: [{question, answer}]` | `400` bad path, `401`, `404` no matching files, `429` |
| 41 | `GET` | `/flashcards/sessions` | Cookie | `useSessionLoaders` | _(none)_ | `sessions: [{session_id, title, last_updated}]` | `401` |
| 42 | `PUT` | `/flashcards/sessions/{session_id}` | Cookie | `useScopedSessionActions` | Body: `{ title: str }` | `status: "updated"` | `401`, `404` |
| 43 | `DELETE` | `/flashcards/sessions/{session_id}` | Cookie | `useScopedSessionActions` | Path: `session_id` | `status: "deleted"` | `401` |
| 44 | `GET` | `/flashcards/latest` | Cookie | `FlashcardPanel` load | Query: `session_id=<uuid>` | `artifact: {artifact_id, flashcards: [...], title, tags}` | `401` |
| 45 | `POST` | `/cards/{card_id}/flashcards/generate` | Cookie + quota | `LessonPanel` card flashcards | Path: `card_id`; Body (optional): `{ context?: str }` | `artifact_id, flashcards: [{question, answer}]` | `401`, `404` card not found, `429` |

---

## 9. Artifacts

| # | Method | Path | Auth | Frontend Caller | Request | Success Response Fields | Error Codes |
|---|---|---|---|---|---|---|---|
| 46 | `GET` | `/artifacts/{artifact_id}` | Cookie | `FlashcardPanel` / `LessonPanel` | Path: `artifact_id` | `artifact: {artifact_id, type, payload, title, tags, saved}` | `401`, `404` |
| 47 | `POST` | `/artifacts/{artifact_id}/save` | Cookie | `FlashcardPanel::handleSaveArtifact` / `LessonPanel::handleSaveArtifactMeta` | Multipart form: `title?: str, tags?: comma-separated str` | `artifact_id, status: "saved"` | `401`, `404` artifact not found |

---

## 10. Usage / Plan

| # | Method | Path | Auth | Frontend Caller | Request | Success Response Fields | Error Codes |
|---|---|---|---|---|---|---|---|
| 48 | `GET` | `/plan/me` | Cookie | usage banner / profile UI | _(none)_ | `plan: {plan_code, limits: {...}}, usage: {ask, upload, lesson, quiz, flashcard, ...}` | `401` |
| 49 | `GET` | `/plan/limits` | Cookie | plan limits UI | _(none)_ | `plan_code, effective_limits: {...}, all_limits: {...}` | `401` |

---

## 11. Admin (role: admin only)

| # | Method | Path | Auth | Frontend Caller | Request | Success Response Fields | Error Codes |
|---|---|---|---|---|---|---|---|
| 50 | `POST` | `/admin/reindex` | Cookie + admin role | Admin panel | _(none)_ | `status: "Reindex completed"` | `401`, `403` insufficient role |
| 51 | `POST` | `/admin/reindex-incremental` | Cookie + admin role | Admin panel | _(none)_ | `status: "Incremental reindex completed"` | `401`, `403` |

---

## 12. WebSocket Endpoints

Auth: JWT sent as `Sec-WebSocket-Protocol` header. On failure → server closes with code `1008`.  
All messages are JSON strings. Frontend: `services/websocket.js`.

### `/ws/ask` — Streaming RAG Chat
**Frontend caller:** `useChatSendMessage::handleSend` via `services/websocket.js::connectWebSocket`

#### Client → Server (send once per query)
```json
{
  "query": "What is photosynthesis?",
  "session_id": "uuid-here",
  "model_name": "mistral-7b"
}
```
`model_name` is optional; `session_id` defaults to `"default"`.

#### Server → Client (streamed messages)
| `type` | Payload | Meaning |
|---|---|---|
| `chunk` | `{ "type": "chunk", "data": "token text" }` | One streamed token from the LLM |
| `end` | `{ "type": "end" }` | Stream complete; full response saved to `chat_history` |
| `error` | `{ "type": "error", "data": "error message" }` | LLM/RAG failure mid-stream |

Close code `1008` = auth failure (expired JWT).

---

### `/ws/lesson` — Lesson Step Streaming
**Frontend caller:** `LessonPanel` WS hook (if active)

#### Client → Server (initial)
```json
{ "session_id": "uuid-here" }
```

#### Server → Client
| `type` | Payload | Meaning |
|---|---|---|
| `lesson_step` | `{ "type": "lesson_step", "step": { id, title, content, ... } }` | Next step to display |
| `lesson_complete` | `{ "type": "lesson_complete" }` | All steps done |
| `error` | `{ "type": "error", "data": "..." }` | Unexpected failure |

#### Client → Server (per step)
```json
{ "action": "complete_step" }
```
120 s timeout per step; server continues without waiting on timeout.

---

### `/ws/quiz` — Interactive Quiz Streaming
**Frontend caller:** `QuizPanel` WS hook (if active)

#### Client → Server (initial)
```json
{ "session_id": "uuid-here", "quiz_id": "uuid-here" }
```

#### Server → Client
| `type` | Payload | Meaning |
|---|---|---|
| `question` | `{ "type": "question", "question": { id, question, options } }` | One question to display |
| `feedback` | `{ "type": "feedback", "question_id": "q1", "result": { correct, correct_option } }` | Grade for submitted answer |
| `quiz_complete` | `{ "type": "quiz_complete" }` | All questions graded |
| `error` | `{ "type": "error", "data": "..." }` | Failure |

#### Client → Server (per question)
```json
{ "answer": "option_a" }
```
120 s timeout per question; server sends null feedback on timeout.

---

### `/ws` — Basic Test Streaming (not used in production UI)
Accepts plain text query strings, returns space-tokenized answer chunks.

---

## 13. Quota Guard Summary

Endpoints gated by `require_quota(action)` — returns `429` when daily limit exceeded.

| Action key | Endpoints |
|---|---|
| `ask` | `POST /ask` |
| `upload` | `POST /files/upload` |
| `lesson` | `POST /lesson-plan/create` |
| `quiz` | `POST /quiz/generate`, `POST /cards/{card_id}/quiz/generate` |
| `flashcard` | `POST /flashcards/`, `POST /cards/{card_id}/flashcards/generate` |

Plan limits (`/plan/limits`) define the per-action daily caps by `plan_code` (`free`, `pro`, etc.).

---

## 14. Session Ownership Guard Summary

Endpoints gated by `validate_session_ownership` or `_assert_session_owner_if_exists`.

| Enforcement | Endpoints | Failure |
|---|---|---|
| `validate_session_ownership` (hard fail on missing) | `DELETE /sessions/{id}`, `PUT /sessions/{id}` | `403` if session owned by another user |
| `_assert_session_owner_if_exists` (allows new sessions) | `GET /history`, `GET /sessions/{id}/content`, `PUT /sessions/{id}/content` | `403` if session exists and owned by another user |

---

## Cross-Reference

| doc | focus |
|---|---|
| [backend-truthmap.md](../backend/docs/backend-truthmap.md) | Route → service/module → DB table mapping |
| [runtime-flow-view.md](runtime-flow-view.md) | UI click → full runtime execution traces with failure paths |
| [python-dependency-graph.md](python-dependency-graph.md) | Static Python import graph; layer view; hotspot modules |
