# Environment Variables

Environment variable names are centralized in `v3/backend/app/core/env_vars.py`.
Frontend/build-time names are centralized in `v3/configs/envNames.mjs`.

## Runtime

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `dev` | Application environment: `dev`, `test`, or `prod`. |
| `APP_DB_FILE` | empty | SQLite database file override. |
| `SECRET_KEY` | `change-me-in-production` | JWT signing secret. Must be set safely outside local/test. |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | JWT lifetime in minutes. |
| `TOKEN_COOKIE_NAME` | `access_token` | Auth cookie name. |
| `AUTH_COOKIE_SECURE` | auto | Whether auth cookies require HTTPS. |
| `AUTH_COOKIE_SAMESITE` | `lax` | Auth cookie SameSite policy. |

## Network Overrides

These override merged config values from `v3/configs/settings.*.json`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `BACKEND_BIND_HOST` | empty | Backend bind-host override. |
| `BACKEND_HOST` | empty | Legacy/shared backend host override. |
| `HOST` | empty | Generic backend bind-host fallback. |
| `BACKEND_PORT` | empty | Backend port override. |
| `PORT` | empty | Generic backend port fallback. |
| `BACKEND_PUBLIC_HOST` | empty | Public backend hostname override. |
| `BACKEND_PROTOCOL` | empty | Public backend HTTP protocol override. |
| `BACKEND_WS_PROTOCOL` | empty | Public backend WebSocket protocol override. |

## Indexing And Retrieval

| Variable | Default | Purpose |
| --- | --- | --- |
| `KB_REINDEX_MODE` | `skip` | Startup KB reindex mode: `skip`, `incremental`, or `full`. |
| `SKIP_KB_REINDEX` | `false` | Legacy flag forcing startup KB reindex to skip. |
| `DISABLE_INDEX_JOB_RECOVERY` | `false` | Disable startup indexing-job recovery. |
| `INDEX_JOB_WORKERS` | `2` | Background indexing worker count. |
| `FAISS_EMBEDDING_DIM` | `768` | Fallback FAISS embedding dimension. |

## Model Providers

| Variable | Default | Purpose |
| --- | --- | --- |
| `MODEL_PROFILE` | empty | Active model-profile override. |
| `OPENAI_API_KEY` | empty | OpenAI API key. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible base URL. |
| `OPENAI_TIMEOUT_SECONDS` | `60` | OpenAI request timeout. |
| `GROQ_API_KEY` | empty | Groq API key. |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | Groq OpenAI-compatible base URL. |
| `GROQ_TIMEOUT_SECONDS` | `60` | Groq request timeout. |

## Optional Features

| Variable | Default | Purpose |
| --- | --- | --- |
| `ALLOW_WS_QUERY_TOKEN` | `false` | Allow deprecated WebSocket query-token fallback. |
| `ENABLE_DEFAULT_USERS` | empty | Force default seed users outside local/dev environments. |
| `ENABLE_INDIC_TRANS2` | `false` | Enable optional IndicTrans2 translation backend. |
| `INDICTRANS2_EN_INDIC_MODEL` | `ai4bharat/indictrans2-en-indic-1B` | IndicTrans2 English-to-Indic model. |
| `INDICTRANS2_INDIC_EN_MODEL` | `ai4bharat/indictrans2-indic-en-1B` | IndicTrans2 Indic-to-English model. |

## Frontend And Test Tooling

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_APP_ENV` | empty | Frontend environment overlay selector. |
| `VITE_API_BASE_URL` | empty | Playwright/test API base URL override. |
| `VITE_WS_BASE_URL` | empty | Playwright/test WebSocket base URL override. |
| `NODE_ENV` | empty | Node/Vite mode fallback for config loading. |
| `PYTEST_CURRENT_TEST` | empty | Pytest marker used to infer test environment. |
| `PYTEST_XDIST_WORKER` | empty | Pytest-xdist worker id for isolated DB names. |
