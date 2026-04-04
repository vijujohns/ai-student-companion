# Deferred Recommendations

- Consider splitting `v3/backend/app/api/routes.py` into smaller domain routers (`auth`, `learning`, `progress`, `admin`) to reduce coupling and improve maintainability.
- Consider fully removing the remaining static import cycle between `v3/backend/app/modules/faiss_store.py` and `v3/backend/app/modules/ingestion.py`.
- No additional deferred recommendations were added during Step 1 approval closure.
- Consider adding an explicit task-intent router so chat requests can be deterministically dispatched across Q&A, lesson, quiz, translation, and future math flows.
- Consider introducing a hybrid retrieval layer with re-ranking/citation scoring on top of the current FAISS-only retrieval baseline.
- Consider adding a dedicated math-solver/validator path instead of relying on the general LLM flow for mathematics-heavy queries.
- No additional deferred recommendations were added during Step 2 approval closure.
- Consider introducing all new orchestration layers behind existing service ports first, to preserve current route contracts and reduce migration risk.
- No additional deferred recommendations were added during Step 3 approval closure.
- Consider using feature flags or configuration toggles for each refactor slice so old and new orchestration paths can run side-by-side during rollout.
- No additional deferred recommendations were added during Step 4 approval closure.
- Consider moving files into the new folders in small phases with import shims/backward-compatible re-exports to avoid sudden path breakage.
- No additional deferred recommendations were added during Step 5 approval closure.
- Consider explicitly pinning runtime dependencies already relied on in the environment but not declared in `v3/backend/requirements.txt` (for example `python-multipart`, `passlib`, and any approved OCR/math packages) to improve reproducibility.
- No additional deferred recommendations were added during Step 6 approval closure.
