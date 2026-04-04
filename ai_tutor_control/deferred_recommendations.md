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
