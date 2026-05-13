# Improvement Goals

This plan is based on the source-derived memory files in `ai_tutor_control/`, especially `gap_analysis.md`, `architecture_review.md`, `ui_review.md`, and `mobile_readiness.md`.

## Product North Star

Transform the current AI tutor from a broad local-first prototype into a stable, coherent, scalable, and mobile-ready learning platform while preserving the working learning workflows already present: chat, knowledge-grounded answers, uploads, lessons, quizzes, flashcards, notes, assessments, progress, collaboration, subscriptions, and admin controls.

## Goal 1: Stability

### Desired Outcome

The system should behave predictably under normal classroom/student usage, fail clearly when dependencies are unavailable, and avoid hidden state corruption across chat, indexing, quota, sessions, and generated learning artifacts.

### Current Drivers

- Large mixed-responsibility files increase regression risk.
- API envelopes and error handling are inconsistent.
- WebSocket disconnect/cancellation paths may not release quota consistently.
- Upload/indexing failures are recorded but not always easy to recover from.
- Manual SQLite migrations and flexible JSON payloads need stronger guardrails.
- LocalStorage auth/session state can become stale or inconsistent.

### Target Capabilities

- Consistent API error envelopes and frontend error presentation.
- Reliable quota accounting across REST, WebSocket, failure, and disconnect paths.
- Clear upload/indexing states with retry/recovery.
- Health checks for DB, FAISS/index freshness, Redis/cache, OCR, model availability.
- Stronger regression coverage around high-risk flows.
- Safer auth/session handling.

### Success Indicators

- Critical user journeys pass automated backend + frontend tests.
- Failed indexing, expired sessions, unavailable model/OCR/cache, and quota exhaustion all produce clear user-facing states.
- No known quota leakage on failed/cancelled generation.
- Core flows can be run repeatedly without stale localStorage/session failures.

## Goal 2: Feature Completeness

### Desired Outcome

Existing feature promises should become coherent product experiences rather than isolated technical capabilities.

### Current Drivers

- Subscription activation is local-only and not payment-backed.
- Student-mentor linking lacks invitation/approval.
- Reminder preferences exist but no durable reminder scheduler is implemented.
- Uploaded document management is incomplete.
- Admin lacks full operational surfaces for users, subscriptions, failed jobs, message catalog, and audit.
- Assignment templates are localStorage-only.

### Target Capabilities

- Complete upload document lifecycle: upload, index, view status, retry, rename/delete, use in learning flows.
- Clear role-based collaboration workflow with invitation/approval.
- Better admin operations for indexing, users, subscriptions, failed jobs, model profiles, and audit.
- Server-backed assignment templates or explicit local-only positioning.
- Real payment integration or a clearly marked mock/subscription mode.
- Reminder scheduler and notification channel if reminders remain in scope.

### Success Indicators

- Each visible feature has a complete first-run, success, empty, error, and recovery state.
- Admin and mentor workflows can be completed without direct DB/file intervention.
- Subscription/reminder/collaboration behavior matches product copy and user expectations.

## Goal 3: Scalability

### Desired Outcome

The backend should be able to evolve beyond a single local process without rewriting the product from scratch.

### Current Drivers

- SQLite write concurrency is limited.
- FAISS/documents and LLM cache are process-local.
- Indexing and long AI jobs run in-process.
- WebSocket generation ties streaming clients to API workers.
- Manual migrations make schema evolution risky.

### Target Capabilities

- Clear service boundaries around identity, learning, knowledge, progress/collaboration, commerce, model runtime.
- Versioned migrations.
- Durable job queue for indexing and long AI jobs.
- Vector store abstraction.
- Production database path, ideally Postgres.
- Request ids, metrics, and audit logs.

### Success Indicators

- Long-running indexing/generation can be monitored, retried, and resumed.
- Data layer can move from SQLite to Postgres behind known repositories/services.
- API workers can scale without divergent indexes/job state.

## Goal 4: UX Improvement

### Desired Outcome

The learning workspace should feel understandable, responsive, accessible, and recoverable, especially around context selection, streaming, uploads, role workflows, and dense progress/assignment screens.

### Current Drivers

- `ChatPanel.jsx` and `RoleHubPanel.jsx` are too broad.
- No route-level navigation or browser history for panels.
- Selected context can be unclear after session/panel changes.
- Upload indexing state needs a better "ready/failed/retry" experience.
- Streaming errors can appear as assistant text.
- Accessibility and mobile layout need systematic review.

### Target Capabilities

- Route-like workspace navigation.
- Persistent learning context bar.
- Dedicated upload/indexing panel or drawer.
- Structured toast/banner error system.
- Split large panels into focused views.
- Keyboard/focus/accessibility pass on core workflows.
- Better mobile breakpoints and stacked layouts.

### Success Indicators

- Users always know active class/subject/content/index status.
- Core panels are navigable by keyboard and usable at desktop/tablet/mobile widths.
- Streaming/API/upload failures are visually distinct from tutor content.
- Large lists are searchable, filterable, and performant.

## Goal 5: Mobile Readiness

### Desired Outcome

The system should expose stable contracts and platform-neutral state/domain logic so a mobile app can be built without re-discovering or duplicating core behavior.

### Current Drivers

- Backend APIs are mostly present but unversioned and inconsistently typed.
- Frontend depends on browser DOM/CSS/localStorage/PDF/Web Speech/service worker.
- No mobile navigation model or secure mobile token strategy.
- Large desktop panels are not React Native portable.

### Target Capabilities

- API versioning or compatibility layer.
- Consistent OpenAPI response models and generated client readiness.
- Pagination for sessions/history/notes/assignments/artifacts.
- Secure auth pattern suitable for mobile.
- Platform-neutral service modules/state reducers.
- Mobile-friendly upload, PDF viewing, notifications, and offline sync strategy.

### Success Indicators

- Mobile client can be planned against documented, stable API contracts.
- Web workspace structure maps cleanly to mobile screens.
- Auth, streaming, uploads, and offline behavior have mobile-safe designs.

## Cross-Cutting Principles

- Preserve working learning flows while improving structure.
- Prefer incremental, testable changes unless a selected strategy explicitly accepts refactor risk.
- Stabilize contracts before building new clients.
- Separate product-completion work from infrastructure-scaling work when possible.
- Use the existing test suite as a safety net and extend it around high-risk gaps.
- Keep `ai_tutor_control/system_memory.md`, `task_tracker.json`, and `progress.md` current as implementation proceeds.
