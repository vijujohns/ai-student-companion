# Gap Analysis

## Missing or Incomplete Features

- No real payment provider integration for subscription activation.
- No invite/approval flow for student-mentor linking.
- No durable server-side notification/reminder delivery; preferences exist but scheduling is not present.
- No deep links or route URLs for workspace panels/sessions.
- No multi-device sync for assignment templates or offline mutation queue.
- No robust document management UI for deleting/renaming uploaded files.
- No admin UI for users, subscriptions, failed jobs, or message catalog.
- No refresh-token flow.

## Inconsistent Patterns

- API routes partially use `ServiceRegistry` and partially call feature modules directly.
- Flashcards expose a mounted router while adjacent quiz/lesson routes live in `routes.py`.
- Frontend sometimes uses `apiFetch`, while Login uses direct fetch to auth endpoints.
- Similar assignment/date/filter helpers are duplicated across `ProgressPanel`, `RoleHubPanel`, and `AssignmentsPanel`.
- Query/task inference exists in both `task_router.py` and `rag.py`.

## Security Risks

- Bearer JWT stored in localStorage despite HttpOnly cookie support.
- WebSocket auth token is sent in subprotocol.
- Password reset uses email + DOB only.
- No observed rate limiting for login/reset/register/ask.
- Uploads need stronger production controls: size limits, malware scanning, content scanning, storage quotas.
- Markdown/html note editing should be reviewed for XSS around rendering and serialization.
- Default users exist in non-production by default; safe for local but dangerous if env is mis-set.
- Relationship linking appears direct by student email.

## Error Handling Gaps

- Some endpoints return envelopes, others return plain data or raw detail strings.
- Background indexing failures are recorded, but user remediation is limited.
- WebSocket disconnect/cancellation paths may not release quota consistently.
- LLM JSON parsing fallbacks exist but can hide model quality failures.
- Offline mutation replay drops 4xx responses without detailed user feedback.

## Logging and Monitoring Gaps

- Debug logging is optional but not a full observability system.
- No request id/correlation id through frontend/backend/model/indexing flows.
- No metrics for token latency, model load time, retrieval quality, index job duration, OCR failures, quota consumption.
- No structured audit events for admin actions beyond some app settings fields.
- No health endpoints for DB, FAISS freshness, Redis/cache, OCR, model availability.

## Data and Schema Gaps

- SQLite is suitable for local/demo but weak for concurrent multi-user production.
- Manual migrations are extensive and hard to validate.
- JSON columns (`meta_json`, settings, payloads) lack typed validation over time.
- Foreign key integrity is not clearly enforced.

## Testing Gaps

- Good breadth exists, but large heuristic modules need targeted tests for edge cases.
- Need more integration tests for upload -> index -> query with OCR/image paths.
- Need tests for quota release on WebSocket errors/disconnects.
- Need frontend accessibility audits beyond component snapshots.
- Need mobile viewport coverage for the full workspace, not just login/visual snapshots.
