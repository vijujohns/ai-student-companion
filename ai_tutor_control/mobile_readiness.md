# Mobile App Readiness

## Current Readiness

The backend is reasonably close to mobile-ready because most features are exposed through JSON REST endpoints plus WebSocket streaming. The frontend is not directly portable to React Native because it is a browser SPA with DOM/CSS/localStorage/PDF/Web Speech assumptions and very large desktop-oriented components.

## API Readiness

Ready-ish:

- Auth, session, chat, lessons, quizzes, flashcards, notes, progress, subscriptions, relationships, assignments, preferences are API-backed.
- WebSocket streaming exists for chat.
- Content references abstract KB vs upload sources.

Needs work:

- Standardize response envelopes and typed response schemas.
- Add pagination for sessions/history/notes/assignments/artifacts.
- Add mobile-friendly upload progress and retry endpoints.
- Add refresh-token/session renewal.
- Add push notification/reminder endpoints if mobile reminders are desired.
- Add API versioning (`/api/v1`).
- Add OpenAPI response models for generated mobile client types.

Implemented Route B API readiness increments:

- Offset pagination metadata is now exposed on mobile-heavy collections: chat sessions, lesson sessions, quiz sessions, flashcard sessions, saved notes, collaboration notes, and assignments.
- The OpenAPI schema now advertises `limit` and `offset` query parameters for these collections.
- Response models include optional pagination metadata while preserving existing top-level array keys for web compatibility.

## State Handling Suitability

Current:

- React local state + localStorage.
- Session ids persisted per feature.
- Offline queue in localStorage.

Mobile needs:

- Central state store or query cache (TanStack Query, Zustand, Redux Toolkit, or platform equivalent).
- Secure token storage (Keychain/Keystore), not localStorage.
- Durable offline queue with conflict handling.
- Explicit navigation state and deep links.

## Secure Mobile Auth Design

Current web auth uses a short-lived JWT returned from login, an HttpOnly `access_token` cookie, and a localStorage bearer token for API and WebSocket compatibility. A mobile client should treat the bearer token as the primary credential and store it only in platform secure storage such as iOS Keychain or Android Keystore.

Recommended mobile flow:

- Login/register returns the same envelope plus `access_token`, `token_type`, `username`, `email`, and `role`.
- Mobile stores `access_token` in secure storage and keeps non-sensitive profile hints in app state.
- REST calls use `Authorization: Bearer <token>` and do not depend on browser cookies.
- WebSocket calls pass auth through the existing `chat.<token>` subprotocol path. Query-string tokens should remain disabled unless explicitly enabled for local debugging.
- On HTTP 401 or WebSocket close code 1008, mobile clears secure storage and returns to login.
- Refresh/session renewal should be added before production mobile release: issue a longer-lived refresh token in secure storage, rotate it on use, and keep access tokens short-lived.

Security constraints:

- Never persist tokens in AsyncStorage, SQLite, logs, crash reports, analytics events, or deep links.
- Do not place tokens in WebSocket URLs because URLs can appear in infrastructure logs.
- Keep role/relationship authorization server-side; mobile UI role checks are convenience only.
- Add device logout by clearing secure storage locally and calling the existing logout endpoint when online.

## UI Portability

Not directly portable:

- DOM APIs, CSS classes, browser PDF embedding, Web Speech API, service worker, localStorage.
- React Icons can map imperfectly; many layouts need native components.

Portable concepts:

- Feature panels map to mobile screens.
- API services can be rewritten with the same endpoints.
- Stream token normalization logic can be reused conceptually.
- Content catalog selectors can be ported.

## Mobile Screen and Capability Map

The existing web workspace can be mapped to a small set of mobile screens while preserving core workflows.

- **Home / Context Selector**: landing screen with class/subject/folder/content state, current study context, and quick access to chat, lessons, notes, and uploads.
- **Chat**: conversational screen with input, streaming response, attachments, and an action sheet for document search, templates, and notes.
- **Document Upload**: upload manager with file queue, progress, retry, indexing status, and a separate collection of processed documents.
- **Viewer**: document/content viewer for PDF pages, knowledge content, and indexed results; can optionally use a native PDF/web view or server-rendered pages.
- **Lessons & Quiz**: screen group for lesson plan sessions, quiz sessions, and flashcards, with pagination and session metadata.
- **Notes & Assignments**: screen for notes, assignments, and student/mentor collaboration artifacts with search/filter and lightweight card layouts.
- **Progress / Insights**: dashboard screen with mastery stats, activity history, and content readiness signals.
- **Role / Admin**: profile and admin screens for user/subscription status, message catalog, audit actions, and operational overviews.
- **Billing / Settings**: subscription, plan status, reminders, and auth/session settings.

Mobile capability requirements:

- **Upload resilience**: background upload support, explicit retry, file size guidance, and queue state visible offline.
- **Offline sync**: durable queue for writes when offline, with user-visible pending state and conflict/retry handling.
- **Notifications**: a mobile reminder strategy backed by push/local notifications, with clear opt-in and server sync for reminder state.
- **Secure auth**: token storage in Keychain/Keystore, not localStorage; refresh token rotation before production mobile release.
- **Streaming UX**: keep backend streaming, but allow fallback to paginated or polling results for poor networks.
- **Native viewers**: avoid browser-only PDF/HTML widgets; prefer native viewers or server-rendered preview pages.
- **State portability**: keep feature logic in platform-neutral services, minimize direct DOM/CSS assumptions in core flows.

## Performance Constraints

- Mobile devices cannot host local GGUF models; backend/cloud model runtime is required.
- Streaming and markdown rendering should be batched.
- Large PDFs need mobile viewer strategy: server-rendered pages, native PDF viewer, or external viewer.
- Uploads need background upload support and size limits.
- Progress/RoleHub screens need pagination/lazy loading.

## Required Refactors

1. Define API DTOs and response models consistently.
2. Extract frontend domain logic from components into platform-neutral service modules.
3. Split ChatPanel/RoleHub into screen-level features.
4. Add server-side pagination/search/filter for large collections.
5. Replace localStorage auth with secure mobile storage.
6. Introduce route/navigation model in web first to mirror mobile screens.
7. Separate PDF/document viewing from chat layout.
8. Build a mobile-safe notification/reminder backend.

## Migration Strategy

Phase 1: API hardening

- Add `/api/v1` routing or compatibility layer.
- Normalize envelopes and error codes.
- Add OpenAPI response models and generated client.
- Add pagination.

Phase 2: Web refactor for portability

- Extract feature services and state reducers.
- Split workspace into routes/screens.
- Remove browser-global assumptions from core logic.

Phase 3: Mobile shell

- Build React Native or Expo app with screens:
  - Login/Register/Reset.
  - Home/Context selector.
  - Chat.
  - Viewer.
  - Lessons.
  - Quiz.
  - Flashcards.
  - Notes.
  - Progress.
  - Role hub.
  - Profile/Billing/Settings.

Phase 4: Native capabilities

- Secure token storage.
- Native file picker/uploads.
- Push/local notifications.
- Native PDF viewer.
- Offline cache and sync.

Phase 5: Production hardening

- Move DB/vector/jobs to production-grade infrastructure.
- Add monitoring, crash reporting, analytics, and API rate limiting.
