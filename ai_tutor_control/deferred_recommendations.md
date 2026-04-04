# Deferred Recommendations

- Consider splitting `v3/backend/app/api/routes.py` into smaller domain routers (`auth`, `learning`, `progress`, `admin`) to reduce coupling and improve maintainability.
- Consider fully removing the remaining static import cycle between `v3/backend/app/modules/faiss_store.py` and `v3/backend/app/modules/ingestion.py`.
- No additional deferred recommendations were added during Step 1 approval closure.
