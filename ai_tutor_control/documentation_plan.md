# Documentation Rebuild Plan

Existing docs were ignored for this analysis. This plan describes what should be rebuilt from source truth.

## Missing Documentation

- System overview and architecture.
- Local setup for backend/frontend/models/Redis/Tesseract.
- Environment variables and config reference.
- API reference with auth and envelope examples.
- WebSocket frame contract.
- Data model/schema reference.
- RAG/indexing pipeline documentation.
- Model profile/admin guide.
- Frontend component/state guide.
- Testing guide.
- Deployment guide.
- Security model and production hardening checklist.
- Mobile API/client guide.
- Troubleshooting runbook.

## Proposed Documentation Structure

```text
docs/
  overview.md
  architecture/
    current.md
    target.md
    data-flow.md
  setup/
    local-dev.md
    models.md
    redis.md
    ocr-tesseract.md
    troubleshooting.md
  backend/
    api.md
    websocket.md
    auth.md
    data-model.md
    migrations.md
    rag.md
    ingestion-indexing.md
    model-manager.md
    subscriptions.md
    collaboration.md
  frontend/
    app-shell.md
    workspace.md
    panels.md
    state.md
    offline-pwa.md
    styling.md
  testing/
    backend.md
    frontend-unit.md
    e2e.md
    visual-regression.md
  operations/
    deployment.md
    monitoring.md
    reindexing.md
    backups.md
    security-hardening.md
  mobile/
    api-readiness.md
    migration-plan.md
```

## Phased Plan

### Phase 1: Source-of-Truth Basics

- Write setup guide from `run.py`, Vite config, requirements, settings.
- Document env vars observed in code.
- Generate API inventory from `routes.py`.
- Document WebSocket frame types.
- Document DB tables from `db.py`.

### Phase 2: Architecture and Flows

- Create architecture diagrams.
- Document startup, ask, upload/index, lesson, quiz, assessment, progress, collaboration flows.
- Define module ownership and boundaries.

### Phase 3: Developer Onboarding

- Write "first task" guide: run backend, frontend, tests, seed users, model setup.
- Add troubleshooting for FAISS, models, Redis, OCR, CORS, ports.
- Add testing commands and test-suite map.

### Phase 4: Product and UX Docs

- Document all user journeys.
- Document role permissions.
- Document panel behavior and empty/error states.

### Phase 5: Production Docs

- Security hardening checklist.
- Deployment topology.
- Backup/restore for SQLite/FAISS/uploads.
- Monitoring/logging plan.
- Migration plan to Postgres/queue/vector service.

## Documentation Rules Going Forward

- Keep docs source-linked to files/functions.
- Treat generated OpenAPI as canonical for endpoint shapes.
- Update docs in the same PR as contract or flow changes.
- Add a docs review item to PR checklist.
- Keep `ai_tutor_control/system_memory.md` updated after major architecture changes.
