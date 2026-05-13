# Module Analysis: Frontend Workspace Components

## `ChatPanel.jsx`

- Purpose: central authenticated workspace controller.
- Inputs: current user, plan/usage, sessions, content tree, uploads, WebSocket stream tokens, panel actions.
- Outputs: chat messages, panel navigation, selected learning context, API/WS calls, PDF viewer state, admin/billing/notes actions.
- Internal logic:
  - Loads sessions and selected learning context.
  - Manages chat send/stream state through hooks and websocket service.
  - Cascades class/subject/folder/content selectors.
  - Uploads files, polls index status, retries reindex.
  - Opens PDF content in split viewer or new tab.
  - Handles translation, notes sidebar, subscription catalog/quote/activation.
  - Handles admin full/incremental reindex and status polling.
- Dependencies: most hooks, `apiFetch`, websocket service, selectors, child panels.
- Interactions: orchestrates almost all user-facing features.
- Risks:
  - Extremely large component with many unrelated responsibilities.
  - Modified in current worktree before this analysis; do not assume clean baseline.
  - Hard to reason about render performance and state coupling.
- Tests: many frontend unit/e2e tests including chat flow, selectors, hooks, visual regression.

## `Login.jsx`

- Purpose: login/register/reset password UI.
- Inputs: email/password/profile/DOB fields.
- Outputs: auth token/user callback, local feedback.
- Dependencies: `apiFetch`-like direct fetch to `/login`, `/register`, `/reset-password`, react-datepicker.
- Risks: direct fetch bypasses some API wrapper behavior; reset flow security is weak backend-side.
- Tests: login e2e.

## `LessonPanel.jsx`

- Purpose: create/regenerate lesson plans, display steps/cards, generate card artifacts.
- Inputs: selected content/session/context, lesson sessions.
- Outputs: plan/cards state, completion events, artifact generation/save.
- APIs: `/lesson-plan/create`, `/lesson-plan`, `/lesson-plan/{id}/cards`, card completion, card quiz/flashcards generation, artifact save.
- Risks: depends on selected content/session alignment from ChatPanel.
- Tests: lesson flow e2e, panel unit tests.

## `QuizPanel.jsx`

- Purpose: generate and submit quizzes, including card-based quiz generation.
- Inputs: active lesson/session/card, selected content, user answers.
- Outputs: quiz payload and score feedback.
- APIs: `/quiz/generate`, `/quiz/latest`, `/quiz/{id}/submit`, `/cards/{card_id}/quiz/generate`.
- Risks: quiz session id is localStorage-driven; stale ids can fetch wrong/missing quizzes.
- Tests: quiz flow e2e, panel unit tests.

## `FlashcardPanel.jsx`

- Purpose: generate flashcards and load/save artifacts.
- Inputs: selected lesson/session/card/content.
- Outputs: flashcard deck state, saved artifact metadata.
- APIs: `/flashcards/`, `/flashcards/latest`, `/cards/{id}/flashcards/generate`, `/artifacts/{id}/save`.
- Risks: old `/flashcards/` router plus artifact routes create two generation paths.
- Tests: panel unit tests.

## `AssessmentPanel.jsx`

- Purpose: subject quiz/question-paper generation and history/attempt UI.
- Inputs: selected class/subject/chapter, difficulty, counts, attempt answers.
- Outputs: generated quiz/paper, attempt result.
- APIs: `/assessment/subject-quiz`, `/assessment/question-paper`, `/assessment/papers`, paper detail/attempt.
- Risks: feature requires high trust in generated content and scoring.
- Tests: assessment backend and frontend panel tests.

## `ProgressPanel.jsx`

- Purpose: student analytics dashboard and study plan.
- Inputs: dashboard, insights, study plan, preferences, assignments.
- Outputs: UI filters, reminder settings updates, study plan item updates, assignment status updates.
- APIs: `/progress/dashboard`, `/progress/insights`, `/progress/study-plan`, `/preferences`, assignment update endpoints.
- Risks: many computed filters/date helpers duplicated with RoleHub/Assignments.
- Tests: progress analytics backend, panel unit tests.

## `RoleHubPanel.jsx`

- Purpose: role-specific hub for students, mentors/parents/teachers, and admin.
- Inputs: current role, linked students/mentors, progress, notes, assignments, model profiles.
- Outputs: relationship linking, notes, assignments, template library localStorage, reports, admin model profile updates.
- APIs: relationships, student progress/notes/assignments, admin model profiles.
- Risks:
  - Very large component with admin, mentor, report, assignment-template logic.
  - Template persistence is localStorage-only and not shared across devices.
- Tests: roles/collaboration backend, large panel tests, e2e coverage.

## Other Components

- `AssignmentsPanel.jsx`: focused student assignment list/update view; duplicates some sorting/filter helpers.
- `NotesPanel.jsx`: editable notes UI with markdown/html conversion; risk around sanitization and content fidelity.
- `SummaryViewer.jsx`: parses structured summaries and saves notes.
- `ProfilePanel.jsx`: profile edit/display.
- `BillingPanel.jsx`: displays current plan/catalog/entitlements/quote data.
- `AdminPanel.jsx`: standalone admin model-profile switcher.
- `LanguagePicker.jsx`: language and preference picker.
- `MessageContent.jsx`: Markdown renderer with GFM/highlight.
- `VoiceControl.jsx`: Web Speech recognition trigger.
- `AppErrorBoundary.jsx`: catches render errors.

## Hooks and Utilities

- Hooks mostly extract ChatPanel mechanics but still depend heavily on caller-provided state setters.
- Utilities cover selectors, content catalog flattening, KB status, session CRUD, speech synthesis, stream token normalization.
- Risks:
  - Several hooks are narrow but coupled to ChatPanel state names.
  - More feature logic could move from large components into tested reducers/services.
