# Smoke Flow Checklist

Task: `P0-T04` Create smoke-flow checklist.

Date: 2026-05-03.

Purpose: provide a lightweight, repeatable baseline checklist for Route B work. This checklist is intentionally practical: it records whether core flows are usable before and after each implementation slice, even while the full automated baseline is currently unstable.

## Known Baseline Context

- Baseline repo state is recorded in `baseline_state.md`.
- Baseline test evidence is recorded in `baseline_test_report.md`.
- Backend full suite status: inconclusive because `.venv\Scripts\python.exe -m pytest v3\test_suite\backend` timed out after about 15 minutes.
- Frontend unit status: failed before tests ran because Vitest fork workers timed out.
- Frontend Playwright status: 15 tests ran; 8 passed, 7 failed.
- Existing dirty state must be preserved:
  - tracked old docs under `ai_tutor_control` are deleted;
  - `v3/frontend/src/components/ChatPanel.jsx` has a pre-existing one-line modification.

## Pre-Run Environment Checks

Record results before each smoke pass.

| Check | Command / Method | Expected | Result |
|---|---|---|---|
| Current branch | `git branch --show-current` | Expected working branch known | Pending |
| Git status | `git status --short` | Only known/intentional changes | Pending |
| Backend Python | `.venv\Scripts\python.exe --version` | Python available | Pending |
| Backend pytest import | `.venv\Scripts\python.exe -m pytest --version` | pytest available | Pending |
| Frontend dependencies | check `v3/frontend/node_modules` | dependencies present | Pending |
| Node/npm | `node --version`, `npm --version` | Node/npm available | Pending |
| Config file | `v3/configs/settings.json` exists | present | Pending |
| App DB | `v3/data/app.db` exists or can initialize | present/created | Pending |
| FAISS data | `v3/data/faiss.index` and metadata exist or load gracefully | present/loads | Pending |

## Backend Runtime Smoke

| Flow | Steps | Expected Result | Result |
|---|---|---|---|
| Backend start | Start backend with normal no-reindex mode | Server starts without blocking KB reindex | Pending |
| Runtime health | `GET /health/runtime` | JSON envelope with `status: ok`, backend reachable | Pending |
| Auth login API | `POST /login` with seeded student credentials | Token/user returned and cookie set | Pending |
| Auth session API | `GET /auth/session` after login | Current user returned | Pending |
| Logout API | `POST /logout` | Cookie cleared, session invalidated client-side | Pending |
| Protected route without auth | call protected endpoint without token | 401 envelope, no server crash | Pending |

## Frontend Runtime Smoke

| Flow | Steps | Expected Result | Result |
|---|---|---|---|
| Frontend start | Start Vite frontend | App loads at configured port | Pending |
| Login page | Open app unauthenticated | Login UI visible | Pending |
| Login flow | Login as seeded student | Workspace appears | Pending |
| Session expiry handling | Force/mock 401 if practical | User is returned to login with session message | Pending |
| Offline indicator | Toggle network/offline if practical | Offline/queued state visible without crash | Pending |

## Critical User Journeys

### 1. Login and Workspace

Steps:

1. Open frontend.
2. Login with `student@example.com` / `student123`.
3. Confirm authenticated workspace is visible.
4. Confirm user role/session state is displayed or available.

Pass criteria:

- Login completes.
- Workspace renders without console-breaking errors.
- No unexpected session-expired loop.

Result: Pending.

### 2. Learning Context Selection

Steps:

1. Load classes.
2. Select a class.
3. Select subject.
4. Select folder/content when available.
5. Confirm selected context persists or is reflected in UI.

Pass criteria:

- Cascading selectors populate.
- Selected content/context is visible.
- PDF/content id is valid for later flows.

Result: Pending.

### 3. Chat Streaming

Steps:

1. With an authenticated session, send a basic study question.
2. Observe WebSocket status/chunk/end behavior.
3. Confirm final assistant message is committed.
4. Refresh/reopen session history if practical.

Pass criteria:

- Message sends once.
- Assistant response streams or returns gracefully.
- Errors appear as operational UI, not as misleading tutor content.
- Session history can be loaded.

Result: Pending.

### 4. Upload and Index Status

Steps:

1. Upload a supported small PDF or image.
2. Confirm upload response includes file/content reference.
3. Observe index status transitions.
4. Retry/reindex if a failed state is available.
5. Confirm uploaded item appears in file tree/content selection.

Pass criteria:

- Upload does not crash.
- Status is understandable: queued/running/indexed/failed.
- Failed status gives a recovery path.

Result: Pending.

### 5. PDF Viewer

Steps:

1. Select a bundled KB PDF or uploaded indexed PDF.
2. Open viewer.
3. Confirm PDF loads in split view or new tab.

Pass criteria:

- PDF endpoint returns file.
- Viewer does not break layout.

Result: Pending.

### 6. Lesson Plan

Steps:

1. Select content/context.
2. Open Lesson panel.
3. Generate or load a lesson plan.
4. Complete one lesson card if cards are present.

Pass criteria:

- Plan is created or clear failure is shown.
- Cards/steps render.
- Completion state is persisted.

Result: Pending.

### 7. Quiz

Steps:

1. Select content/context or an active lesson card.
2. Generate or load a quiz.
3. Submit answers.
4. Review score/feedback.

Pass criteria:

- Questions render with options.
- Submit returns scoring result.
- Incorrect/missing quiz states are handled clearly.

Result: Pending.

### 8. Flashcards

Steps:

1. Select content/context or active lesson card.
2. Generate or load flashcards.
3. Save artifact metadata if available.

Pass criteria:

- Cards render front/back content.
- Save action is clear and succeeds or fails gracefully.

Result: Pending.

### 9. Notes

Steps:

1. Open Notes panel.
2. Create/save a note.
3. Reopen note.
4. Edit and delete note.

Pass criteria:

- CRUD works for authenticated user.
- Markdown/editor content remains usable.

Result: Pending.

### 10. Assessment

Steps:

1. Open Assessment panel.
2. Generate a subject quiz or question paper.
3. Record an attempt if applicable.
4. View saved paper/history.

Pass criteria:

- Generated assessment renders.
- Attempt recording works.
- History/detail APIs are usable.

Result: Pending.

### 11. Progress and Study Plan

Steps:

1. Open Progress panel.
2. Load dashboard, insights, study plan, preferences.
3. Update a study-plan item if available.
4. Update reminder settings if visible.

Pass criteria:

- Dashboard data loads.
- Empty states are understandable.
- Updates persist or fail gracefully.

Result: Pending.

### 12. Role Collaboration

Steps:

1. Login as mentor/teacher/parent/admin if seeded credentials or test setup exists.
2. Load role hub.
3. Link or view student roster.
4. Create/update/delete assignment or collaboration note.

Pass criteria:

- Role-specific UI appears.
- Authorization prevents invalid access.
- Notes/assignments persist.

Result: Pending.

### 13. Admin Controls

Steps:

1. Login as admin.
2. Open admin/model profile controls.
3. Read active model profile.
4. Trigger or inspect reindex status only if safe for the environment.

Pass criteria:

- Admin-only controls are protected.
- Model profile read/update works or fails with clear error.
- Reindex controls do not block normal app usage.

Result: Pending.

## Automated Baseline Commands

Use these as baseline commands, with known current caveats.

```powershell
.venv\Scripts\python.exe -m pytest v3\test_suite\backend
```

Current caveat: full backend suite timed out after about 15 minutes.

```powershell
cd v3\frontend
npm test
```

Current caveat: Vitest fork workers timed out before tests ran.

```powershell
cd v3\frontend
npm run test:e2e
```

Current caveat: Playwright baseline is 8 passed / 7 failed.

## Per-Phase Smoke Record Template

Copy this section after each phase.

```text
Phase:
Date:
Branch:
Commit:
Tester:

Backend health:
Frontend health:
Critical journeys passed:
Critical journeys failed:
Known baseline failures unchanged:
New regressions:
Notes:
Decision: proceed / fix before proceeding
```

## Release Gate

Before marking a phase complete:

- No new critical regression is introduced compared with `baseline_test_report.md`.
- Any failing automated tests are either pre-existing baseline issues or documented new known issues.
- Login, chat, context selection, and at least one generated learning flow are manually smoke-tested or explicitly blocked.
- `task_tracker.json` and `progress.md` are updated.
