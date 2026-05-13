# Module Analysis: Frontend Shell and Services

## `src/App.jsx`

- Purpose: top-level app shell and auth/session bootstrap.
- Inputs: login result, backend health, online/offline events, install prompt, density settings.
- Outputs: Login screen or authenticated workspace; global session-expired handling.
- Internal logic:
  - Probes `/health/runtime`.
  - Calls `/auth/session` to bootstrap cookie/bearer sessions.
  - Tracks online/offline and offline queue status.
  - Handles shell menu and density.
  - Passes user identity into `ChatPanel`.
- Dependencies: React, icons, `ChatPanel`, `Login`, PWA helpers.
- Risks:
  - App shell and session logic are coupled.
  - No route-based navigation, so deep linking is limited.
- Tests: frontend `App.test.jsx`, e2e login/session expiry.

## `src/main.jsx`

- Purpose: React mount and service worker registration.
- Inputs: DOM root.
- Outputs: rendered React tree.
- Risks: minimal.
- Tests: covered indirectly.

## `src/services/api.js`

- Purpose: central HTTP wrapper.
- Inputs: API path and fetch options.
- Outputs: fetch `Response`, offline cached response, or queued mutation response.
- Internal logic:
  - Resolves backend URL from `configs/settings.json`.
  - Sends bearer token from localStorage and `credentials: include`.
  - Dispatches `session:expired` on 401.
  - Caches successful GET JSON in localStorage.
  - Queues offline mutations in localStorage and flushes on online.
  - Parses message envelope errors.
- Dependencies: browser fetch/localStorage/navigator, shared config.
- Interactions: every frontend component/hook uses this for REST.
- Risks:
  - localStorage token is an XSS risk.
  - Offline mutation queue replays without conflict resolution/idempotency keys.
  - GET cache can become stale; no TTL currently visible.
- Tests: `services.test.jsx`, e2e session expiry/offline-adjacent tests.

## `src/services/websocket.js`

- Purpose: WebSocket connection manager.
- Inputs: socket type, message payload, callbacks, localStorage token.
- Outputs: active socket(s), callback events, session expiry dispatch.
- Internal logic:
  - Maintains socket/callback maps by type.
  - Builds WS base URL from config.
  - Uses `chat.<token>` subprotocol for auth.
  - Normalizes JSON frames into callback messages.
  - Emits backend health hints after unexpected closes.
- Risks:
  - Token in WebSocket subprotocol.
  - Global singleton sockets can surprise components if multiple mounts compete.
  - Some strings show encoding corruption in source.
- Tests: stream token/lifecycle unit tests, WS session expiry e2e.

## `src/services/pwa.js` and `public/sw.js`

- Purpose: PWA install prompt and service worker registration/caching.
- Inputs: browser PWA events, static asset requests.
- Outputs: install prompt state, cached app resources.
- Risks:
  - Offline API support is separate from service worker; cache invalidation must be checked after build changes.
- Tests: indirect.

## Global CSS

- `src/index.css`: app shell, density, health/network UI, global layout tokens.
- `src/components/style.css`: workspace/panel/component styling.
- Risks:
  - Very large component CSS file; style ownership is not modular.
  - Responsiveness/accessibility issues are harder to localize.
