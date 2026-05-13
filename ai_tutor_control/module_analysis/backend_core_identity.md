# Module Analysis: Backend Core, Identity, and Persistence

## `core/config_loader.py`

- Purpose: Central config access for app env, models, RAG, network, CORS, Redis.
- Inputs: `v3/configs/settings.json`, environment variables.
- Outputs: dictionaries/scalars consumed by backend and frontend config-dependent code.
- Risks: config is JSON-only and not schema-validated; runtime errors are delayed until access.
- Tests: exercised indirectly by startup and frontend Vite config tests.

## `core/debug_logger.py`

- Purpose: Optional structured debug logs.
- Inputs: `DEBUG_LOGGING`, log messages/fields.
- Outputs: console/logging output when enabled.
- Risks: PII can leak if callers pass raw user/query data; currently some query snippets are logged.
- Tests: indirect only.

## `modules/db.py`

- Purpose: SQLite storage layer and migrations.
- Inputs: SQL statements, `APP_DB_FILE`, app env.
- Outputs: DB connections and initialized/migrated schema.
- Internal logic:
  - Resolves DB path to `v3/data/app.db` unless overridden.
  - Creates all current tables in `init_db`.
  - Runs backward-compatible migrations for users, plans, profiles, session content, subscriptions, file management, lesson cards, lesson plans, assessments, preferences, app settings, progress analytics, relationships.
  - Seeds message catalog, subscription catalog, and default users.
- Dependencies: sqlite3, filesystem, config loader.
- Interactions:
  - Almost every backend module imports `get_connection`.
  - Acts as shared schema owner without an external migration framework.
- Risks/tech debt:
  - Monolithic migration file with hand-written schema drift handling.
  - SQLite limits concurrent writes under chat, indexing, progress, and assessment activity.
  - `check_same_thread=False` plus multiple module-level threads requires disciplined transaction use.
  - No explicit foreign-key enforcement seen in connection setup.
- Tests:
  - `test_migration_scripts.py`, many feature tests exercise schema.

## `modules/auth.py`

- Purpose: JWT auth and cookie management.
- Inputs: identifier/password, JWT token, env secret settings.
- Outputs: token payloads, access token, HttpOnly cookie.
- Internal logic:
  - Authenticates by email first, username fallback.
  - Uses `python-jose` JWT with configurable expiry and algorithm.
  - Rejects fallback secret outside development/test/local.
  - Sets cookie with secure/samesite based on env.
- Risks:
  - Frontend also stores bearer token in localStorage, increasing XSS blast radius.
  - No refresh token; all session expiry is hard logout.
- Tests: `test_auth.py`, `test_session_security.py`, session expiry tests.

## `modules/user_manager.py`

- Purpose: user CRUD-ish operations and password hashing.
- Inputs: profile fields, email, DOB, password.
- Outputs: user dictionaries and DB rows.
- Internal logic:
  - PBKDF2-SHA256 with random salt.
  - Seeds `student` and `admin` local users unless production-like env blocks it.
  - Registration uses email as username for downstream compatibility.
  - Password reset requires email + DOB.
  - Profile update rejects email changes and writes audit log.
- Risks:
  - Email-as-username transition creates mixed legacy/new identifiers.
  - DOB-based password reset is weak for production.
  - No account lockout/rate limiting.
- Tests: auth/profile/reset coverage in backend tests.

## `modules/dependencies.py`

- Purpose: FastAPI auth, role, quota, and session ownership guards.
- Inputs: HTTP request, bearer header/cookie, session id.
- Outputs: current user payload or HTTP errors.
- Risks:
  - Session ownership only checks `chat_history`; empty/new sessions need separate handling in route helpers.
  - Role guard is exact string match; no role hierarchy.
- Tests: auth, identity access, session security.

## `modules/ws_auth.py`

- Purpose: WebSocket token extraction.
- Inputs: WebSocket headers, cookies, `Sec-WebSocket-Protocol`.
- Outputs: user payload or auth failure.
- Risks:
  - Token in subprotocol can be exposed in tooling/logging.
  - Must stay synchronized with frontend `chat.<token>` convention.
- Tests: websocket/session expiry tests.

## `modules/messages.py`

- Purpose: message catalog lookup and response envelopes.
- Inputs: message id and payload.
- Outputs: standardized `message` metadata.
- Risks:
  - Some routes still return plain dicts/strings, so frontend error handling must remain defensive.
- Tests: contract envelope/snapshot tests.
