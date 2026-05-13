# Module Analysis: Knowledge, Commerce, Progress, Collaboration

## `modules/ingestion.py`

- Purpose: extract, chunk, summarize, and index PDFs/images.
- Inputs: PDF/image file path/bytes.
- Outputs: chunks with metadata, summaries, FAISS documents.
- Internal logic:
  - Uses pypdf for PDF text extraction.
  - Applies OCR for images and OCR text from PDFs where available.
  - Chunks by configured size/overlap.
  - Infers chapter/topic/source metadata from path/text.
  - Builds extractive summaries and writes to summary store.
  - Adds documents to FAISS.
- Risks:
  - CPU-heavy and synchronous inside background thread pool.
  - OCR availability is environment-dependent.
  - Metadata inference from paths can fail for inconsistent naming.
- Tests: ingestion behavior indirectly through file management/RAG/reindex tests.

## `modules/ocr.py`

- Purpose: OCR support and readiness status.
- Inputs: image path or bytes.
- Outputs: extracted text or status flags.
- Risks:
  - Requires local Tesseract install; dependency failures are handled but reduce feature quality.
  - OCR result quality affects image-upload learning.
- Tests: `test_image_pipeline.py`, OCR status endpoint tests.

## `modules/file_management.py`

- Purpose: user upload lifecycle and indexing job management.
- Inputs: authenticated user, upload file, class/subject/folder/display name, reindex scope/file id.
- Outputs: uploaded file rows, content references, background index jobs, status/tree DTOs.
- Internal logic:
  - Creates per-user storage roots using email hash.
  - Validates folder/display names and file types.
  - Stores PDF/image uploads under `v3/app/uploads`.
  - Encodes content refs as KB or upload ids.
  - Queues indexing jobs and runs them in a `ThreadPoolExecutor`.
  - Recovers queued/running jobs at startup.
  - Enforces user-vs-admin visibility on file tree/status.
- Risks:
  - In-process job queue is lost on process crash except DB recovery.
  - No virus scanning or content moderation.
  - Upload size/type controls need production review.
- Tests: `test_file_management.py`, smart reindexing, knowledge seam.

## `modules/kb_sync.py`

- Purpose: knowledge-base reindex orchestration.
- Inputs: force/incremental/file modes, KB directory.
- Outputs: reindex job progress and FAISS/metadata rebuilds.
- Risks:
  - Full rebuild can be long and resource-heavy.
  - Single in-process progress state is not multi-worker safe.
- Tests: smart reindexing/retrieval tests.

## `modules/image_pipeline.py`

- Purpose: summarize/extract image-upload content.
- Inputs: image path.
- Outputs: normalized OCR text, keywords, fallback/model summary.
- Risks: model usage for image summary is text-only OCR-derived, not true vision.
- Tests: `test_image_pipeline.py`.

## `modules/policy.py`

- Purpose: plan-aware quota and usage accounting.
- Inputs: user id, action.
- Outputs: allowed/denied decisions, usage counters, plan snapshots.
- Internal logic:
  - Ensures active usage period.
  - Reads plan entitlements and active class subscriptions.
  - Increments/release usage for actions.
- Risks:
  - Quota increments before generation means failures need manual release; some disconnect paths may not release.
  - Entitlement model is local, not payment-provider-backed.
- Tests: subscription/features, auth/quota, plan summary.

## `modules/subscriptions.py`

- Purpose: subscription catalog, quote, activation.
- Inputs: class names, promo codes, user id.
- Outputs: class rates, promotion calculations, user class subscriptions.
- Risks:
  - Activation appears local only; no real payment verification.
  - Pricing hard-seeded in DB migration.
- Tests: `test_subscription_features.py`.

## `modules/analytics.py`

- Purpose: learning analytics, mastery, dashboard, insights, study plan.
- Inputs: activity events, quiz/assessment/assignment data, study plan item states.
- Outputs: dashboard/insight/study-plan DTOs and history snapshots.
- Internal logic:
  - Logs learning time.
  - Updates mastery.
  - Calculates streaks and recent activity.
  - Combines assignments and assessment summaries into plans.
- Risks:
  - Large module with mixed analytics, study plan generation, assignment history.
  - Date parsing from labels/due strings can be brittle.
- Tests: `test_progress_analytics.py`.

## `modules/adapters/default_services.py` and `interfaces/service_ports.py`

- Purpose: service facade and ports for higher-level application seams.
- Inputs/outputs: feature-specific DTOs through protocol methods.
- Internal logic:
  - Implements identity access, relationship collaboration, progress, knowledge, commercial, learning sessions.
  - `routes.py` uses registry for several route groups.
- Risks:
  - Partial adoption: some routes use ports, others still import modules directly.
  - Services are concrete and DB-backed; no dependency injection container.
- Tests: identity/knowledge/learning-session seam tests, roles collaboration.

## Relationships and Collaboration

- Implemented mostly in `default_services.py` with routes in `routes.py`.
- Features:
  - Link student by email.
  - List students for parent/teacher/admin.
  - List mentors for student.
  - CRUD collaboration notes.
  - CRUD mentor assignments.
  - Student progress visibility for authorized mentors.
- Risks:
  - Relationship authorization is app-level SQL logic; no row-level DB constraints.
  - Bulk assignment behavior lives in a large frontend component.
- Tests: `test_roles_collaboration.py`, role hub frontend tests.
