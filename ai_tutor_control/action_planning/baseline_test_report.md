# Baseline Test Report

Tasks:

- `P0-T02`: Run backend baseline tests.
- `P0-T03`: Run frontend baseline tests.

Date: 2026-05-03.

## Summary

Baseline testing was executed without changing product code. The current baseline is not green.

- Backend full suite: inconclusive, timed out after 15 minutes using the repo `.venv`.
- Frontend unit suite: failed before running tests because Vitest fork workers timed out.
- Frontend Playwright e2e: ran 15 tests; 8 passed and 7 failed.

These outcomes are recorded as baseline evidence. They should not be treated as regressions from future implementation work unless a later task worsens them.

## Backend Baseline

### Command 1

```powershell
python -m pytest v3\test_suite\backend
```

### Result

Failed immediately because the system Python does not have `pytest` installed.

```text
C:\Python314\python.exe: No module named pytest
```

### Command 2

```powershell
.venv\Scripts\python.exe -m pytest v3\test_suite\backend
```

### Result

Timed out after approximately 15 minutes.

```text
command timed out after 905347 milliseconds
```

### Backend Baseline Status

Inconclusive / blocked by full-suite runtime timeout.

### Notes

- The repo-level virtual environment exists and can invoke Python.
- The command did not complete within the baseline window, so pass/fail counts were not available.
- No backend files were modified.

## Frontend Unit Baseline

### Command

```powershell
npm test
```

Run from:

```powershell
v3\frontend
```

### Result

Failed before tests executed because Vitest fork workers timed out while starting.

```text
Test Files  no tests
Tests       no tests
Errors      18 errors
```

Representative error:

```text
Error: [vitest-pool]: Failed to start forks worker
Caused by: Error: [vitest-pool-runner]: Timeout waiting for worker to respond
```

### Frontend Unit Baseline Status

Failed / blocked by Vitest worker startup timeout.

### Notes

- `node_modules` exists under `v3/frontend`.
- No frontend files were modified.

## Frontend Playwright Baseline

### Command

```powershell
npm run test:e2e
```

Run from:

```powershell
v3\frontend
```

### Result

Playwright ran 15 tests.

```text
8 passed
7 failed
```

### Failed Tests

- `chat-flow.spec.js`: chat sends and receives streamed reply.
- `lesson-flow.spec.js`: lesson plan generation flow works.
- `login-flow.spec.js`: user can login from UI.
- `new-sprint-coverage.spec.js`: upload tree shows indexed + processing selectable states.
- `visual-regression.spec.js`: chat workspace visual baseline.
- `visual-regression.spec.js`: lesson panel visual baseline.
- `visual-regression.spec.js`: quiz panel visual baseline.

### Failure Themes

- Several functional e2e tests timed out at `page.goto("/")`, waiting for `http://127.0.0.1:4174/`.
- Visual baselines failed because screenshot dimensions/pixels differ from expected snapshots:
  - chat expected `1280x753`, received `1280x720`;
  - lesson expected `1280x843`, received `1280x879`;
  - quiz expected `1280x827`, received `1280x945`.
- WebServer console output included WebSocket errors and session-expiry close code `1008` warnings during the run.

### Frontend E2E Baseline Status

Partially failing: 8 passed, 7 failed.

## Baseline Interpretation

The current test baseline is unstable/incomplete before Route B implementation work begins:

- Backend requires either a longer test window, targeted suite slicing, or investigation into long-running tests.
- Frontend unit tests require Vitest worker startup troubleshooting.
- Frontend e2e has a mix of navigation timeouts and visual snapshot drift.

## No Code Change Confirmation

No product code was changed while collecting these results.
