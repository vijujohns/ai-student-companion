## Step 1
- Date: 2026-04-04
- Status: Completed after user approval.
- Confirmed current step in `execution_plan.md` as `IN PROGRESS` before closure.
- Mapped backend entrypoints: `v3/backend/run.py` -> `v3/backend/app/main.py`.
- Identified REST and WebSocket surfaces in `v3/backend/app/api/routes.py` and `v3/backend/app/api/websocket.py`.
- Identified service registry domains: `identity`, `relationships`, `progress`, `knowledge`, `commercial`, `learning`.
- Traced the RAG pipeline across `ingestion.py`, `faiss_store.py`, `kb_sync.py`, `rag.py`, and `model_manager.py`.
- Verified local model inventory and task-based model profiles from `v3/configs/settings.json`.
- Captured Backend Truth Map, Dependency Graph, and Runtime Flow in `ai_tutor_control/architecture.md`.
- Approval received from user; Step 1 closed without starting Step 2.

## Step 2
- Date: 2026-04-04
- Status: Completed after user approval.
- Confirmed Step 2 was the active step and kept it `IN PROGRESS` until approval.
- Compared the current system against the required upgrade areas: task router, retrieval upgrade, generators, image pipeline, and math + translation.
- Classified capabilities into `Supported`, `Partial`, and `Missing` based on verified routes/modules and current runtime behavior.
- Stored the detailed analysis in `ai_tutor_control/architecture.md`.
- Approval received from user; Step 2 closed without starting Step 3.

## Step 3
- Date: 2026-04-04
- Status: Completed after user approval.
- Confirmed Step 3 as the active step and kept `execution_plan.md` at `IN PROGRESS` until approval.
- Designed a modular upgrade architecture centered on three upgrade pillars: multi-modal ingestion, multi-index RAG, and task routing.
- Preserved the existing FastAPI routes, service ports, and session flows as the compatibility shell.
- Saved the proposed target architecture in `ai_tutor_control/architecture.md`.
- Approval received from user; Step 3 closed without starting Step 4.

## Step 4
- Date: 2026-04-04
- Status: Completed after user approval.
- Confirmed Step 4 as the active step and kept `execution_plan.md` at `IN PROGRESS` until approval.
- Defined a safe, additive upgrade sequence that preserves current routes, sessions, auth, quotas, and UI flows.
- Kept the plan focused on compatibility-first rollout with feature flags and validation gates.
- Saved the plan in `ai_tutor_control/architecture.md`.
- Approval received from user; Step 4 closed without starting Step 5.

## Step 5
- Date: 2026-04-04
- Status: Completed after user approval.
- Confirmed Step 5 as the active step and kept `execution_plan.md` at `IN PROGRESS` until approval.
- Defined a new modular backend/frontend structure aligned with the approved architecture.
- Added an old-to-new mapping so the upgrade can proceed without ambiguity or breaking moves.
- Saved the structure plan in `ai_tutor_control/architecture.md`.
- Approval received from user; Step 5 closed without starting Step 6.

## Step 6
- Date: 2026-04-04
- Status: Completed after user approval.
- Confirmed Step 6 as the active step and kept `execution_plan.md` at `IN PROGRESS` until approval.
- Reviewed declared backend dependencies in `v3/backend/requirements.txt` and frontend dependencies in `v3/frontend/package.json`.
- Cross-checked the configured Python environment package list against runtime imports and planned upgrade needs.
- Identified both already-available dependencies and suggested missing/should-be-pinned dependencies without installing anything.
- Saved the dependency report in `ai_tutor_control/architecture.md`.
- Approval received from user; Step 6 closed without starting Step 7.

## Step 7
- Date: 2026-04-04
- Status: Completed.
- Confirmed Step 7 as the active non-approval-gated implementation step.
- Added `v3/backend/app/modules/task_router.py` as a compatibility-first routing shell that classifies `/ask` and `/ws/ask` requests into existing task categories (`qa`, `summary`, `lesson`, `quiz`, `flashcards`, etc.).
- Integrated the router minimally into `v3/backend/app/api/routes.py` and `v3/backend/app/api/websocket.py` without changing the public response envelope.
- Extended `v3/backend/app/modules/rag.py` with optional task-aware model selection and task-aware cache keys so routed requests do not collide in cache.
- Added focused backend coverage in `v3/test_suite/backend/test_task_router.py`.
- Full regression verification completed after the code change:
  - Backend: `533 passed, 1 skipped, 3 warnings`
  - Frontend unit: `169 passed`
  - Frontend Playwright: `15 passed`
- During the required full test run, one unrelated backend regression surfaced in `extract_text_from_pdf`; it was fixed minimally by normalizing leftover line-break whitespace in `v3/backend/app/modules/ingestion.py`.
- Step 7 closed; Step 8 is now the next pending step.

## Step 8
- Date: 2026-04-04
- Status: Completed.
- Confirmed Step 8 as the active non-approval-gated implementation step.
- Added `v3/backend/app/modules/retrieval_orchestrator.py` to provide compatibility-first logical multi-index planning (`curriculum`, `upload`, `session`, `artifact`) and hybrid lexical + vector ranking.
- Upgraded `v3/backend/app/modules/faiss_store.py` so `search()` now supports task-aware hybrid retrieval and optional detailed retrieval packets without breaking existing callers.
- Integrated the retrieval upgrade into `v3/backend/app/modules/rag.py` so routed tasks now pass retrieval intent into the RAG search path.
- Added focused backend coverage in `v3/test_suite/backend/test_retrieval_upgrade.py`.
- No new dependencies were added; the hybrid lexical layer was implemented with the existing stack.
- Full regression verification completed after the code change:
  - Backend: `535 passed, 1 skipped, 3 warnings`
  - Frontend unit: `169 passed`
  - Frontend Playwright: `15 passed`
- Step 8 closed; Step 9 is now the next pending step.

## Step 9
- Date: 2026-04-04
- Status: Completed.
- Confirmed Step 9 as the active non-approval-gated implementation step.
- Added `v3/backend/app/modules/generator_executor.py` as a compatibility-first execution layer for `quiz`, `flashcards`, and `summary` tasks.
- Integrated the generator executor into `v3/backend/app/api/routes.py` and `v3/backend/app/api/websocket.py` for explicit generator requests while preserving the earlier implicit compatibility path.
- Reused the existing quiz generator, flashcard generator, and saved-ingestion summary flow instead of introducing new dependencies or breaking route contracts.
- Added focused backend coverage in `v3/test_suite/backend/test_generator_executor.py`.
- Full regression verification completed after the code change:
  - Backend: `538 passed, 1 skipped, 3 warnings`
  - Frontend unit: `169 passed`
  - Frontend Playwright: `15 passed`
- Step 9 closed; Step 10 is now the next pending step.

## Step 10
- Date: 2026-04-04
- Status: Completed.
- Confirmed Step 10 as the active non-approval-gated implementation step.
- Added `v3/backend/app/modules/image_pipeline.py` as a compatibility-first OCR/image extraction helper that derives titles, keywords, and student-friendly summaries from uploaded images.
- Upgraded `v3/backend/app/modules/ingestion.py` so `ingest_image()` now saves an image summary and indexes enriched OCR chunks (`Image`, `Source`, `Keywords`, `OCR Summary`) without changing the existing upload flow.
- Added focused backend coverage in `v3/test_suite/backend/test_image_pipeline.py`.
- No new dependencies were added; the implementation reuses the existing OCR stack and current summary storage path.
- Full regression verification completed after the code change:
  - Backend: `541 passed, 1 skipped, 3 warnings`
  - Frontend unit: `169 passed`
  - Frontend Playwright: `15 passed`
- Step 10 closed; Step 11 is now the next pending step.

## Step 11
- Date: 2026-04-04
- Status: Completed.
- Confirmed Step 11 as the active non-approval-gated implementation step.
- Added `v3/backend/app/modules/math_executor.py` for SymPy-backed math solving with safe fallback to the existing model path for broader prompts.
- Added `v3/backend/app/modules/translation_executor.py` and `v3/backend/app/modules/utility_executor.py` so routed `math` and `translation` requests now use dedicated utility executors behind `/ask` and `/ws/ask`.
- Upgraded `v3/backend/app/modules/translation.py` with an optional IndicTrans2-compatible backend path, while preserving the current `deep-translator` fallback when local IndicTrans2 support is not enabled.
- Added focused backend coverage in `v3/test_suite/backend/test_math_translation_executor.py`.
- Dependency check result for this step:
  - `sympy` was already present in the active environment and is now explicitly pinned in `v3/backend/requirements.txt`
  - IndicTrans2 runtime support is optional/config-driven; the current environment continues to fall back safely when that backend is unavailable
- Full regression verification completed after the code change:
  - Focused backend Step 11 suites: `77 passed, 3 warnings`
  - Backend: `545 passed, 1 skipped, 3 warnings`
  - Frontend unit: `169 passed`
  - Frontend Playwright: `15 passed`
- Step 11 closed; Step 12 is now the next pending step.

## Step 12
- Date: 2026-04-04
- Status: Completed after user approval.
- Implemented Step 12C smart reindexing as a compatibility-first indexing upgrade without redesigning the ingestion stack.
- Added chunk classification and metadata enrichment in `v3/backend/app/modules/ingestion.py` so indexed chunks now carry `chapter`, `topic`, `type`, `modality`, and a logical `index_name`.
- Extended `v3/backend/app/modules/faiss_store.py` to persist logical multi-index buckets (`concept_index`, `summary_index`, `qa_index`, `formula_index`, `image_index`) while keeping the existing FAISS contract backward compatible.
- Updated `v3/backend/app/modules/retrieval_orchestrator.py` so task-aware retrieval now prefers the matching logical index (for example math -> `formula_index`, lesson/explanation -> `concept_index`, quiz -> `qa_index`, OCR/image -> `image_index`).
- Extended `v3/backend/app/modules/kb_sync.py` and the existing admin reindex endpoints to return reindex progress stats for full or selective rebuilds while preserving the current `/admin/reindex` response status contract.
- Added focused coverage in `v3/test_suite/backend/test_smart_reindexing.py`.
- Verification evidence collected after implementation:
  - Targeted smart-indexing/regression suites: `111 passed, 1 skipped, 3 warnings`
  - Backend full suite: `548 passed, 1 skipped, 3 warnings`
  - Frontend unit: `169 passed`
  - Frontend Playwright: `15 passed`
- Example grounding check after the change showed task alignment working as intended:
  - Math query top result -> `formula_index` (`Formula: speed = distance / time`)
  - Lesson/explanation query top result -> `concept_index` (`Concept: Photosynthesis is the process by which plants make food using sunlight.`)
- Waiting for user approval before closing Step 12 or moving to later steps.
- Added Step 12B grounding fixes in `v3/backend/app/modules/rag.py` and `v3/backend/app/modules/model_manager.py`:
  - retrieved chunks are now logged with metadata for debugging
  - context is reduced to a bounded top 3–5 chunks with deduplication
  - context is formatted with explicit `[CONTEXT START]` / `[CONTEXT END]` chunk boundaries
  - the strict prompt now requires the exact fallback phrase `I don't have enough information in the provided material.`
  - the old general-knowledge fallback path was removed for RAG answers
  - a no-context / ungrounded-answer fail-safe now blocks unsupported answers
- Added targeted grounding regression coverage in `v3/test_suite/backend/test_rag.py`.
- Validation evidence after the grounding fix:
  - Targeted grounding/retrieval suites: `42 passed, 3 warnings`
  - Backend full suite: `551 passed, 1 skipped, 3 warnings`
  - Frontend unit: `169 passed`
  - Frontend Playwright: `15 passed`
- Manual validation check for the requested physics-style query `What is refraction?`:
  - Before fix: the system returned an external unsupported explanation despite no matching indexed material.
  - After fix: the same query returned `I don't have enough information in the provided material.` when no relevant context was retrieved.
- Added Step 12D feature correction + stabilization without changing the already-fixed RAG core:
  - `v3/backend/app/modules/quiz.py` now preserves `correct_answer` and `explanation`, normalizes option/answer labels more reliably, and extracts structured quiz JSON even when wrapped in fenced text.
  - `v3/backend/app/modules/ocr.py` now exposes safe, patchable OCR fallbacks for missing dependencies and logs clear progress markers (`Image extracted for OCR`, `OCR completed ...`) during extraction.
  - `v3/backend/app/modules/model_manager.py` now returns safe fallback text when local/cloud generation raises runtime errors instead of bubbling crashes back to the caller.
- Added focused regression coverage in `v3/test_suite/backend/test_feature_stabilization.py` for quiz answer retention, structured quiz parsing, OCR progress logging, and model-failure fallback behavior.
- TDD validation evidence for Step 12D:
  - Initial focused repro before the fix: `4 failed`
  - Focused stabilization suite after the fix: `4 passed, 3 warnings`
  - Backend full suite after Step 12D: `555 passed, 1 skipped, 3 warnings`
  - Frontend unit after Step 12D: `169 passed`
  - Frontend Playwright after Step 12D: `15 passed`

## Step 13
- Date: 2026-04-05
- Status: In progress (approval required).
- Scope kept strictly to optimization only: no new routes, no feature expansion, and no architecture redesign.
- Retrieval precision tuning:
  - selected task-tuned context windows after evaluation within the requested `3–5` range: `quiz/assessment = 3`, `lesson/qa/math = 4`, `summary = 5`
  - explanation-style queries now route retrieval toward concept-heavy material, quiz requests toward `qa_index`, and math requests toward `formula_index`
  - zero-signal / low-value chunks are now filtered out during final ranking instead of being kept only because of source/index bonuses
- Query rewriting / re-ranking:
  - added lightweight query variants (original query + keyword query + task-specific rewrites such as `refraction definition` and `refraction explanation example`)
  - merged variant retrieval results and re-ranked them with metadata-aware scoring so the best grounded 3–5 chunks survive while duplicates/noise are removed
- Context structuring / prompt refinement:
  - context blocks are now grouped into labeled sections such as `Concept`, `Example`, `Formula`, and `Question Bank`
  - explanation prompts now ask for a step-by-step teacher-style answer with examples from context
  - summary prompts now enforce concise key-topic coverage
  - quiz prompts now reinforce no-ambiguity / answer-must-match-context behavior
- Added focused regression coverage in `v3/test_suite/backend/test_precision_rag_optimization.py`.
- Validation evidence collected after the optimization pass:
  - Focused Step 13 precision suites: `30 passed, 3 warnings`
  - Backend full suite: `559 passed, 1 skipped, 3 warnings`
  - Frontend unit: `169 passed`
  - Frontend Playwright: `15 passed`
- Manual dataset validation evidence:
  - query rewriting now produces clean explanation variants such as `refraction definition` and `refraction explanation example`
  - ranked sample dataset results showed the expected primary indexes:
    - explanation -> `concept_index`
    - quiz -> `qa_index`
    - math -> `formula_index`
  - structured context now renders explicit teaching sections (`Concept`, `Example`, `Question Bank`)
- Approval status: WAITING.

## Operational Step: Indexing Control Enhancement
- Date: 2026-04-05
- Status: Completed after approval and follow-up hardening.
- Goal kept minimal and compatibility-first:
  - prevent KB indexing on backend startup by default
  - allow explicit startup control via CLI/env flag
  - provide non-blocking admin controls for full / incremental / single-file reindex
  - preserve session usability while indexing runs in the background
- Backend changes made:
  - `v3/backend/run.py` now accepts `--reindex=true|incremental|full|skip`
  - `v3/backend/app/main.py` now resolves startup indexing mode to `skip` by default and defers any requested startup reindex until after the app finishes booting
  - `v3/backend/app/modules/kb_sync.py` now launches background reindex jobs with a `job_id`, exposes job-aware progress snapshots, and keeps background KB refresh lightweight by using extractive summaries during reindex ingestion instead of immediate local-LLM summarization
  - `v3/backend/app/api/routes.py` now returns immediate `started` responses for `/admin/reindex`, `/admin/reindex/full`, `/admin/reindex/incremental`, and `/admin/reindex/file`, plus job-status polling endpoints
- Frontend/admin UX changes made:
  - `v3/frontend/src/components/ChatPanel.jsx` now tracks `job_id`, polls live status by job, and keeps the admin UI responsive during background indexing
  - existing admin status UI remains compatible with full / incremental / file-triggered reindex flows
- Root cause and hardening note:
  - the remaining `run.py --reindex=true` instability came from startup-time background reindex work beginning too early and immediately entering the heavier summary-generation path while the app was still booting
  - this was fixed by deferring startup reindex launch until after `Application startup complete` and by using a fast extractive summary path for background reindex jobs
- Fresh verification evidence collected on 2026-04-05:
  - Focused regression coverage after the hardening: `14 passed, 3 warnings in 169.84s`
  - Backend full suite: `567 passed, 1 skipped, 3 warnings in 352.03s`
  - Frontend full unit suite: `171 passed in 68.12s`
  - Playwright e2e: `15 passed in 43.3s`
  - Manual startup without reindex: backend reached `/health/runtime` successfully and reported `"kb_reindex_mode":"skip"`
  - Manual startup with `run.py --reindex=true`: startup completed successfully, `/health/runtime` remained reachable with `"kb_reindex_mode":"incremental"`, and the background incremental reindex finished without the earlier early exit
- Approval status: COMPLETED.

## Step 17
- Date: 2026-04-05
- Status: Completed after approval.
- Scope kept strictly compatibility-first and limited to the approved enhancement only:
  - post-login context popup with class/subject selection or Explorer Mode
  - global context persistence with edit flow
  - background content preparation after upload with student-friendly status messaging
  - context enforcement for guided study features without redesigning the app shell
  - cleanup of redundant per-page context selectors
  - student-safe Explorer Mode chat behavior
- Backend changes made:
  - added `ContextSelectionRequest` in `v3/backend/app/schemas/request.py`
  - extended `user_preferences` persistence/migration in `v3/backend/app/modules/db.py` with `context_mode`, `class_name`, `subject_name`, `folder_name`, and `content_id`
  - added `GET /context` and `POST /context` in `v3/backend/app/api/routes.py`
  - added Explorer Mode utility routing and safe refusal handling in `v3/backend/app/modules/utility_executor.py` and `v3/backend/app/modules/task_router.py`
- Frontend changes made:
  - `v3/frontend/src/components/ChatPanel.jsx` now prompts the student with a learning-context modal after login, supports `Proceed in Explorer Mode`, persists the selected context, renders a context summary/edit bar, and shows friendly background preparation progress after upload
  - `v3/frontend/src/hooks/useChatSendMessage.js` now dispatches Explorer chat as `task: "explorer"` without binding to file context
  - `v3/frontend/src/components/style.css` now includes the modal, banner, gate, and processing-state styling for the new workflow
  - `v3/frontend/src/utils/kbSelectors.js` now uses student-friendly wording (`being prepared`) instead of technical indexing language
- Compatibility stabilization completed:
  - refined gating so existing plan-action lesson/quiz flows still work without breaking prior behavior
  - kept assessment access compatible after the initial over-gating regression was identified and corrected
  - updated Playwright specs and visual baselines to match the approved new modal workflow
- Validation evidence collected after implementation:
  - Focused backend context / Explorer regressions: `3 passed, 79 deselected, 3 warnings`
  - Backend full suite: `570 passed, 1 skipped, 3 warnings in 301.01s`
  - Frontend unit suite: `173 passed (17 files)`
  - Frontend production build: success (`vite build`)
  - Frontend Playwright / UI regression suite: `15 passed (40.5s)`
- User-facing result:
  - students now choose a learning context once after login or continue in Explorer Mode for general educational chat
  - uploads prepare in the background with clear, non-technical progress messaging
  - guided study tools stay locked until an appropriate class/subject context is selected, while general chat remains available in Explorer Mode
- Approval status: COMPLETED.
