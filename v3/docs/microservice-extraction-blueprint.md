# Microservice Extraction Blueprint (Post-Feature Gap Closure)

## Date
2026-04-01

## Goal
Define when and how to extract services from the current FastAPI monolith without regressing chat, lesson, quiz, flashcards, upload/indexing, and role collaboration flows.

## Current State Assessment

### What is working well in monolith mode
- Single deployment unit keeps local-first developer flow fast.
- Shared SQLite access is simple and predictable for feature velocity.
- Existing route + module boundaries already map cleanly to future service seams.

### What currently increases coupling risk
- Central API router imports many modules directly.
- Shared DB tables create implicit cross-feature contracts.
- Some cross-module dependencies are cyclic (notably ingestion <-> faiss store).
- Role/collaboration, subscriptions, progress, and learning actions now coexist in one process with broad blast radius.

### Extraction decision
Do not do a big-bang split. Start with a modular-monolith hardening pass, then carve out low-coupling domains behind internal APIs.

## Service Boundaries (Target)

### 1) Identity + Access Service
Scope:
- Login, register, reset-password, profile
- JWT/session validation
- Role and relationship management (teacher/parent/student links)

Primary tables:
- users
- student_relationships
- user_preferences

External contract surface:
- /login, /register, /logout, /auth/session, /profile, /reset-password
- /relationships/*

### 2) Learning Session Service
Scope:
- Chat sessions/history metadata
- Lesson sessions/plans/cards
- Quiz sessions and submission state
- Flashcard sessions and artifacts metadata linkage

Primary tables:
- chat_history
- lesson_plans
- lesson_cards
- lesson_card_progress
- lesson_quizzes
- lesson_quiz_results
- learning_artifacts

External contract surface:
- /sessions*
- /lesson-plan*
- /quiz*
- /flashcards*
- /artifacts*

### 3) Knowledge + Ingestion Service
Scope:
- File upload lifecycle
- Indexing jobs and status
- OCR/image ingestion
- FAISS/vector store operations

Primary tables:
- uploaded_files
- indexing_jobs
- file_index_status

Storage:
- knowledge_base files
- faiss.index
- metadata.json

External contract surface:
- /files/*
- /classes, /subjects, /folders, /contents
- /pdf
- /ocr/status

### 4) Analytics + Progress Service
Scope:
- Activity logs
- Mastery computation
- Dashboard composition
- Student progress read models for mentor/guardian views

Primary tables:
- learning_time_log
- mastery_scores
- collaboration_notes

External contract surface:
- /progress/*
- /students/{student}/progress
- /students/{student}/notes
- /collaboration/notes

### 5) Commercial Service
Scope:
- Plan entitlements and usage
- Subscription catalog, quote, activation
- Quota decisions

Primary tables:
- usage_counters
- subscription_catalog
- subscription_promotions
- subscription_plan_features
- user_class_subscriptions

External contract surface:
- /plan/*
- /subscription/*
- quota middleware integration

## Edge Gateway Strategy
Keep one public API gateway (current FastAPI app) during migration.

Responsibilities:
- Preserve existing REST and WS contracts unchanged.
- Route internally to extracted services via HTTP/gRPC adapters.
- Maintain envelope response format compatibility.

## Migration Phases

### Phase 0: Modular Monolith Hardening (required)
- Introduce service interfaces per domain under backend/app/modules/interfaces.
- Remove direct cross-domain table reads where possible.
- Break ingestion/faiss cycle.
- Add contract tests for all public endpoints and envelope shapes.

Exit criteria:
- No new cyclic imports across domain packages.
- Contract tests stable and green.

### Phase 1: Extract Analytics + Progress (first candidate)
Why first:
- Mostly append/read workloads.
- Lower risk than auth and session ownership paths.

Steps:
1. Add internal client from gateway to analytics service.
2. Move /progress routes and progress helpers behind client.
3. Keep DB replicated or shared read-write temporarily.
4. Shadow-read dashboards for 1 release before cutover.

Rollback:
- Feature flag to route requests back to in-process module.

### Phase 2: Extract Knowledge + Ingestion
Why second:
- Heavy compute and IO path, clear operational isolation benefits.

Steps:
1. Move indexing worker and OCR pipeline out of gateway process.
2. Keep file metadata APIs backward compatible.
3. Convert indexing jobs to queue-backed execution.
4. Keep /files and /pdf contracts stable via gateway proxy.

Rollback:
- Switch queue consumer off and restore in-process job executor.

### Phase 3: Extract Commercial Service
Why third:
- Strong data ownership boundary and policy rules can be centralized.

Steps:
1. Move plan and subscription logic.
2. Introduce usage decision API (allow/deny + message_id).
3. Replace direct quota checks in gateway with remote policy call and local fallback cache.

### Phase 4: Extract Identity + Access
Why fourth:
- Highest sensitivity and cross-cutting auth dependency.

Steps:
1. Introduce token introspection endpoint and key rotation strategy.
2. Move relationship management APIs.
3. Migrate auth cookie issuance and session bootstrap paths.

### Phase 5: Extract Learning Session Service (optional final)
Why last:
- Core product behavior and largest state surface.

Steps:
1. Move session CRUD and lesson/quiz/flashcard lifecycle.
2. Keep websocket gateway in edge process initially.
3. Introduce event stream for async state updates.

## Data Ownership Matrix

| Domain | Owner Service | Migration Pattern |
|---|---|---|
| users, relationships, preferences | Identity + Access | Move-first with dual-read window |
| sessions, lessons, quizzes, artifacts | Learning Session | Last-mile split with strict contract tests |
| uploaded_files, indexing_jobs, file_index_status | Knowledge + Ingestion | Queue-first extraction |
| learning_time_log, mastery_scores, collaboration_notes | Analytics + Progress | Early extraction with shadow reads |
| usage + subscriptions | Commercial | Policy API + cached fallback |

## Runtime SLO Targets (post-extraction)
- p95 /ask HTTP fallback under 1800 ms (model-dependent paths excluded).
- p95 /progress/dashboard under 300 ms.
- p95 /relationships/my-students under 150 ms.
- Index job queue delay under 10 s median.
- Gateway 5xx rate under 0.5% per day.

## Feature Flag Plan
- service.analytics.remote_enabled
- service.ingestion.remote_enabled
- service.commercial.remote_enabled
- service.identity.remote_enabled
- service.learning.remote_enabled

Each flag must support:
- runtime toggle
- fail-open or fail-back mode
- per-route metrics split by local vs remote path

## Observability Requirements
- Correlation id propagated from gateway to all services.
- Structured logs with route, user role, tenant/user id hash, latency, status.
- Golden dashboards per domain route family.
- Contract mismatch alarms on envelope shape drift.

## Test Strategy for Safe Extraction

### Contract tests (must stay green across phases)
- Envelope fields and message catalog behavior.
- Auth/session status and role checks.
- Session ownership and relationship-gated access.
- Upload/index and progress endpoint schemas.

### Shadow traffic tests
- Replay selected production-like requests to local and remote implementations.
- Compare status code, envelope message_id, and key payload fields.

### Chaos/failure tests
- Service unavailable -> gateway fallback path.
- Slow downstream -> timeout + graceful degradation.
- Partial DB migration state -> read consistency checks.

## “Extract Only If” Triggers
Start phase 1 only when at least two conditions hold for two consecutive weeks:
- CPU sustained above 65% during peak usage windows.
- p95 latency regression > 20% on two or more route families.
- Deployment frequency blocked by unrelated domain test failures.
- Incident blast radius crosses domain boundaries at least twice.

If triggers are not met, continue modular monolith and defer extraction.

## Immediate Next Actions (No Breakage)
1. Add domain interface layer and adapters inside monolith.
2. Add route-family latency metrics tags by domain.
3. Add envelope contract snapshot tests for all critical endpoints.
4. Refactor ingestion/faiss cycle before any service split.

## Reference Mapping to Existing Files
- Runtime contracts: v3/docs/api-bridge.md
- Runtime click-to-execution paths: v3/docs/runtime-flow-view.md
- Static dependency baseline: v3/docs/python-dependency-graph.md
- Current main router seam: v3/backend/app/api/routes.py
