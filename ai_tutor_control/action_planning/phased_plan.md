# Route B Phased Plan: Balanced Incremental Improvement

Selected route: Route B, Balanced Incremental Improvement.

Planning horizon: 6-10 weeks, assuming incremental delivery and regular verification after each phase.

## Phase 0: Execution Baseline and Safety Net

### Objective

Establish a reliable baseline before changing product behavior so future progress is measurable and regressions are visible.

### Scope

- Existing backend and frontend test suites.
- Current dirty worktree awareness.
- Planning artifacts in `ai_tutor_control/action_planning`.
- High-risk flow inventory.

### Tasks

- Record current git state and pre-existing modified/deleted files.
- Run or document baseline backend tests.
- Run or document baseline frontend unit/e2e tests.
- Identify failing/flaky tests before implementation.
- Create a lightweight release checklist for every phase.
- Confirm critical smoke flows: login, chat, content selection, upload status, lesson, quiz, notes, progress.

### Dependencies

- Existing test environment must be runnable.
- Local model/FAISS/OCR availability may affect AI-heavy tests.

### Risks

- Tests may require local services/models not currently available.
- Existing dirty changes may affect baseline results.

### Deliverables

- Baseline test report.
- Known failing/flaky test list.
- Smoke-flow checklist.
- Updated `task_tracker.json` and `progress.md`.

### Success Criteria

- Team knows current system health before feature/refactor work.
- Future failures can be distinguished from pre-existing failures.

## Phase 1: Stabilize Core Runtime and User Trust

### Objective

Make the current system safer and clearer without large structural changes.

### Scope

- Auth/session handling.
- REST/WebSocket error handling.
- Quota consumption/release.
- Upload/indexing status and retry.
- Health/runtime diagnostics.
- Frontend error presentation.

### Tasks

- Normalize error envelopes for priority endpoints used by chat, upload/indexing, lessons, quizzes, notes, auth, progress.
- Add or harden quota release on WebSocket errors, disconnects, and generation failures.
- Add dependency health checks for DB, FAISS metadata freshness, cache/Redis, OCR, model config availability.
- Improve frontend API/WebSocket error display so operational failures do not appear as tutor content.
- Make upload/indexing status states explicit: queued, running, indexed, failed, retrying.
- Add targeted tests for quota leakage, session expiry, upload/index retry, and health responses.
- Review localStorage session clearing and stale session behavior.

### Dependencies

- Phase 0 baseline.
- Understanding of current `apiFetch`, `websocket.js`, `routes.py`, `websocket.py`, `policy.py`, `file_management.py`.

### Risks

- Changing envelope shape can break frontend assumptions.
- WebSocket lifecycle changes can affect streaming UX.
- Indexing retry behavior may expose old inconsistent job rows.

### Deliverables

- Stabilized error handling for critical paths.
- Health endpoint expansion or new health detail endpoint.
- Quota-safety tests.
- Upload/index retry UX and tests.

### Success Criteria

- Critical failures produce clear UI states.
- No known quota leakage on failed/cancelled generation.
- Upload/index failures can be retried from UI.
- Existing core tests still pass or known failures are documented.

## Phase 2: Backend Boundary and Contract Cleanup

### Objective

Reduce backend change risk by grouping routes, strengthening contracts, and expanding service boundaries incrementally.

### Scope

- `app/api/routes.py`.
- Request/response schemas.
- Service ports and default services.
- API envelope and DTO normalization.
- First mobile/API contract preparation.

### Tasks

- Split `routes.py` into domain routers while preserving existing public paths.
- Prioritize routers: auth/profile, chat/session/context, knowledge/files, lessons/artifacts, quiz/flashcards, assessment, progress/preferences, collaboration, commerce, admin.
- Move direct route logic into service methods where service ports already exist or are natural.
- Add response models/envelope helpers for priority endpoints.
- Create `/api/v1` compatibility design document, but avoid breaking current paths during this phase.
- Consolidate task inference responsibilities between `task_router.py` and RAG retrieval inference where safe.
- Add contract tests for moved route groups.

### Dependencies

- Phase 1 stabilized contracts.
- Existing backend tests must remain the safety net.

### Risks

- Route import cycles.
- Public path changes by accident.
- Inconsistent envelope migration across route groups.

### Deliverables

- Domain router modules.
- Preserved existing endpoint paths.
- Expanded service facade usage.
- Contract tests for moved groups.
- API contract notes for mobile readiness.

### Success Criteria

- `routes.py` no longer acts as the only massive API file.
- Existing frontend works without endpoint changes.
- Contract tests pass for high-use route groups.

## Phase 3: Frontend Workspace Decomposition and UX Clarity

### Objective

Make the web workspace easier to understand, maintain, test, and adapt to mobile.

### Scope

- `ChatPanel.jsx`.
- `RoleHubPanel.jsx`.
- Workspace navigation/state.
- Shared utilities.
- Upload/context/error UI.
- Core CSS responsiveness/accessibility.

### Tasks

- Introduce route-like workspace navigation state for chat, lessons, quiz, flashcards, notes, assessment, progress, role hub, profile, billing, admin.
- Build a persistent `LearningContextBar` showing class/subject/folder/content/index status.
- Extract upload/indexing UI into a dedicated component/drawer.
- Extract structured error/toast/banner mechanism for API and WebSocket failures.
- Split ChatPanel responsibilities into focused child components/services without changing behavior.
- Extract shared assignment/date/filter utilities used by Progress, RoleHub, Assignments.
- Decompose RoleHub into role-specific sections or subcomponents.
- Add keyboard/focus and mobile viewport tests for core workspace flows.
- Improve mobile breakpoints for sidebar, chat, viewer, and dense panels.

### Dependencies

- Phase 1 frontend error patterns.
- Phase 2 route stability helps frontend service cleanup.

### Risks

- `ChatPanel.jsx` is pre-existing modified in the worktree; edits require careful diff review.
- Large component extraction can cause subtle state regressions.
- CSS changes may affect visual regression snapshots.

### Deliverables

- Smaller workspace components.
- Learning context bar.
- Dedicated upload/indexing UI.
- Shared utility modules.
- Accessibility/mobile test coverage.

### Success Criteria

- Users can always identify active context and indexing readiness.
- Core workflows remain functional after component split.
- Visual/unit/e2e tests pass or snapshots are intentionally updated.

## Phase 4: Complete Priority Product Workflows

### Objective

Turn the most visible incomplete capabilities into coherent workflows while staying within the improved architecture.

### Scope

- Uploaded document lifecycle.
- Role collaboration.
- Admin operations.
- Subscription mode clarity.
- Assignment templates.
- Reminder implementation decision.

### Tasks

- Add uploaded document rename/delete/manage APIs and UI.
- Add relationship invite/approval or explicitly scoped admin/mentor linking rules.
- Add server-backed assignment templates or clearly mark templates as local-only.
- Add admin job/failure visibility and retry controls.
- Add admin user/subscription/message-catalog/audit surfaces as scoped MVPs.
- Decide payment approach: real provider integration, mock mode, or deferred with clear UI labeling.
- Decide reminder approach: server scheduler, local-only reminders, or deferred with UI removal.
- Add tests for each completed workflow.

### Dependencies

- Phase 2 backend routers/services.
- Phase 3 UI decomposition to avoid adding more logic to huge panels.

### Risks

- Product decisions affect scope significantly.
- Payment/reminder integrations can balloon if not tightly scoped.
- Relationship changes can affect authorization assumptions.

### Deliverables

- Complete uploaded document lifecycle.
- Clear collaboration workflow.
- Admin operational MVP.
- Subscription/reminder decisions implemented or visibly deferred.

### Success Criteria

- Visible product promises match implemented behavior.
- Admin/mentor/student workflows do not require DB/manual intervention.
- Tests cover success, empty, error, and permission states.

## Phase 5: Mobile Contract and Platform Readiness

### Objective

Prepare stable backend and frontend foundations for a future mobile app without building the full mobile app in this route.

### Scope

- API DTOs and response models.
- Pagination.
- Secure auth strategy.
- Platform-neutral frontend services/state.
- Mobile design mapping.

### Tasks

- Define `/api/v1` compatibility or versioning implementation plan.
- Add pagination to sessions, history, notes, assignments, artifacts where needed.
- Add OpenAPI response models for mobile-critical endpoints.
- Generate or document typed client contract.
- Design secure mobile token/session strategy.
- Extract platform-neutral service/domain logic from browser components.
- Document mobile screen map from web workspace.
- Define mobile upload, PDF viewer, offline sync, and notification strategy.

### Dependencies

- Phase 2 contract cleanup.
- Phase 3 frontend decomposition.

### Risks

- Versioning can create duplicated endpoint maintenance.
- Pagination can require frontend changes to existing lists.
- Mobile auth decisions may require backend token changes.

### Deliverables

- Mobile API readiness docs.
- Pagination for key collections.
- Typed contract/OpenAPI coverage.
- Platform-neutral service modules where practical.

### Success Criteria

- A mobile app team can build against documented stable contracts.
- Web remains compatible with contract changes.
- Core data-heavy endpoints are mobile-safe.

## Phase 6: Operational Scalability Preparation

### Objective

Prepare the next architecture step without forcing a full infrastructure migration during Route B.

### Scope

- Job queue abstraction.
- DB migration plan.
- Vector store abstraction.
- Observability.
- Deployment/runbooks.

### Tasks

- Introduce interfaces around indexing jobs and vector store operations where low risk.
- Draft Postgres migration plan and schema ownership map.
- Draft durable queue migration plan for indexing and long AI jobs.
- Add request/correlation ids across API logs and frontend error reports.
- Add metrics/log hooks for model latency, token streaming, index jobs, OCR failures, quota usage.
- Document backup/restore for SQLite/FAISS/uploads.
- Document production hardening checklist.

### Dependencies

- Earlier phase boundaries make abstraction safer.

### Risks

- Too much infrastructure work could exceed Route B scope.
- Metrics/logging can expose sensitive query/user data if not scrubbed.

### Deliverables

- Queue/vector/DB migration designs.
- Initial observability hooks.
- Operational runbooks.

### Success Criteria

- Route C-style infrastructure work can begin later without rediscovering the system.
- Operators have basic visibility into failures and performance.

## Phase Review Loop

After each phase:

- Re-run targeted and smoke tests.
- Update `task_tracker.json` statuses.
- Update `progress.md`.
- Re-evaluate risks and next phase scope.
- Add, remove, or split tasks if new constraints appear.
- Update `system_memory.md` if architecture or contracts change materially.
