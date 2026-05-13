# Strategic Route Options

This file intentionally presents multiple distinct strategies. No detailed phased plan should be created until a route or hybrid route is selected.

## Decision Matrix

| Route | Strategy | Effort | Risk | Impact | Best For |
|---|---|---:|---:|---:|---|
| A | Quick Stabilization | S, 2-4 weeks | Low-Medium | Medium | Making the current app safer fast |
| B | Balanced Incremental Improvement | M, 6-10 weeks | Medium | High | Best default path for product maturity |
| C | Full Refactor / Clean Architecture | L, 12-20+ weeks | High | Very High | Preparing for serious scale and long-term maintainability |
| D | Mobile-First Transformation | L, 10-18+ weeks | Medium-High | High | Prioritizing mobile app delivery and stable API contracts |

## Route A: Quick Stabilization

### Description

Stabilize the current monolith with focused fixes and test coverage, avoiding major architecture changes. This route treats the current FastAPI + React structure as acceptable for now and focuses on reliability, security hygiene, and UX recovery states.

### What Will Be Improved

- API error consistency for high-traffic endpoints.
- WebSocket quota release and generation failure handling.
- Upload/indexing status clarity and retry behavior.
- Health checks for critical dependencies.
- Auth/session expiry handling.
- Frontend error presentation for streaming/API failures.
- Regression tests around chat, upload/index/query, quota, auth expiry.
- Small UX wins: context visibility, failure banners, safer empty states.

### What Will NOT Be Addressed

- No major split of `routes.py`, `ChatPanel.jsx`, or `RoleHubPanel.jsx`.
- No durable external queue.
- No Postgres migration.
- No full mobile app architecture.
- No comprehensive payment/reminder/collaboration rebuild.
- No deep clean architecture conversion.

### Estimated Effort

Small: 2-4 weeks.

### Risk Level

Low to Medium.

Risk stays lower because changes are narrow, but some risk remains around shared chat/indexing/auth flows.

### Impact Level

Medium.

This improves trust and day-to-day usability but does not solve the deeper scaling and maintainability limits.

### When This Route Is Ideal

- You need a more reliable demo or pilot quickly.
- Users are already testing the product and hitting rough edges.
- Timeline is short.
- The current architecture is acceptable for the next milestone.
- You want to reduce regression risk before larger work.

## Route B: Balanced Incremental Improvement

### Description

Use a staged modernization path: stabilize first, then gradually extract clearer backend route/service boundaries and frontend workspace slices while completing the most visible product gaps. This is the best default route if the goal is to improve the product without freezing delivery for a large rewrite.

### What Will Be Improved

- All Route A stabilization items.
- Backend route grouping by domain: auth, chat, knowledge, lessons, assessment, progress, commerce, collaboration, admin.
- More complete service-port adoption.
- API response model normalization for priority endpoints.
- Upload/document management lifecycle.
- Role/collaboration flow improvements.
- Workspace navigation and context bar.
- Split high-risk frontend components into smaller panels/hooks/services.
- Shared utilities for assignments/date/filter logic.
- Accessibility and mobile-responsive improvements for core screens.
- API/mobile contract preparation without building full mobile app yet.

### What Will NOT Be Addressed

- Full Postgres/vector-store/queue migration may be designed but not fully implemented.
- Full React Native mobile app is not delivered.
- Local LLM runtime remains in-process unless explicitly added as a later phase.
- Payment provider integration may be scoped as optional depending on business priority.

### Estimated Effort

Medium: 6-10 weeks.

### Risk Level

Medium.

Risk is controlled by phased delivery, but refactoring large files and contracts requires disciplined tests.

### Impact Level

High.

This route materially improves stability, maintainability, UX, and mobile readiness while preserving the working product.

### When This Route Is Ideal

- You want the strongest product/engineering return without a full rewrite.
- You expect continued feature development.
- You want to prepare for mobile and scale but still ship web improvements.
- You can invest several weeks and want visible progress each phase.

## Route C: Full Refactor / Clean Architecture

### Description

Restructure the backend and frontend around explicit domain boundaries and production-grade infrastructure. This route prioritizes long-term maintainability, scalability, and clean separation over near-term feature velocity.

### What Will Be Improved

- Backend modular architecture with domain routers, application services, repositories, and versioned contracts.
- Migration from manual SQLite migrations toward Alembic and likely Postgres.
- Durable queue for indexing and long-running AI work.
- Vector store abstraction and possible external vector DB option.
- Model runtime isolation from API workers.
- Strong observability: request ids, structured logs, metrics, job dashboards, audit trails.
- Frontend workspace split into route-like feature areas with shared state/query cache.
- Stronger typed API client and DTO discipline.
- Better test pyramid around services/contracts.

### What Will NOT Be Addressed

- Fast short-term feature delivery.
- Full mobile app UI unless combined with Route D.
- Some existing UI polish may be deferred while architecture is reshaped.
- Feature gaps like payment/reminders may wait behind platform refactor.

### Estimated Effort

Large: 12-20+ weeks.

### Risk Level

High.

Large refactors can destabilize working behavior unless aggressively phased with compatibility layers.

### Impact Level

Very High.

Best long-term architecture payoff, especially for multi-user production scale.

### When This Route Is Ideal

- The product is moving toward production scale or institutional deployment.
- You can tolerate slower visible feature delivery.
- You want to support multiple clients, multiple workers, and reliable operations.
- The team is ready to invest in architecture as a primary deliverable.

## Route D: Mobile-First Transformation

### Description

Prepare and/or build around mobile delivery first. This route hardens API contracts, extracts platform-neutral frontend logic, introduces mobile-safe auth/state patterns, and reshapes web navigation to map cleanly to mobile screens.

### What Will Be Improved

- API versioning or compatibility layer.
- Consistent response DTOs and OpenAPI models for generated clients.
- Pagination for mobile-heavy lists: sessions, history, notes, assignments, artifacts.
- Secure token strategy suitable for mobile.
- Mobile-friendly upload progress/retry and document viewing strategy.
- Web workspace route/navigation model aligned to mobile screens.
- Extraction of browser-independent domain services and state reducers.
- React Native/Expo app foundation if selected as part of execution.
- Push/local notification design for reminders.

### What Will NOT Be Addressed

- Full backend production scalability unless combined with Route C.
- Deep cleanup of every web component; work focuses on mobile-critical surfaces.
- Payment provider and admin operations may remain secondary.
- Existing desktop UX may improve only where it overlaps mobile restructuring.

### Estimated Effort

Large: 10-18+ weeks.

### Risk Level

Medium to High.

Risk depends on whether this includes actual mobile app implementation or only mobile readiness foundations.

### Impact Level

High.

This route creates the clearest path to a native/mobile product and forces API discipline.

### When This Route Is Ideal

- Mobile app delivery is the next major business milestone.
- Web is already acceptable enough for now.
- You need stable API contracts before hiring/building mobile.
- You want web refactors that directly reduce mobile duplication.

## Route E: Product Completion First

### Description

Complete the visible unfinished product promises before deeper architectural work. This route focuses on making subscriptions, reminders, role collaboration, document management, admin operations, and assignment templates feel complete.

### What Will Be Improved

- Real or clearly mocked subscription/payment flow.
- Reminder scheduler and notification workflow.
- Student linking invitation/approval.
- Uploaded file rename/delete/manage UI.
- Admin surfaces for users, failed jobs, subscriptions, message catalog, audit.
- Server-backed assignment templates.
- Better empty/onboarding states for student, mentor, parent/teacher, admin.
- Targeted tests for each completed workflow.

### What Will NOT Be Addressed

- Major backend scalability.
- Major frontend architecture cleanup beyond what each feature needs.
- Mobile app foundations except where feature APIs require it.
- Full replacement of SQLite/in-process jobs.

### Estimated Effort

Medium to Large: 8-14 weeks.

### Risk Level

Medium.

Feature breadth touches many modules, but changes can be isolated if architecture is not heavily altered.

### Impact Level

High for product completeness, Medium for engineering foundation.

### When This Route Is Ideal

- Users or stakeholders care most about completing promised workflows.
- The current architecture can support the next launch.
- You need a more marketable product before investing in deeper infrastructure.

## Recommended Default

Route B is the recommended default unless there is a hard deadline or a hard mobile mandate.

Why:

- Route A may leave too much structural debt.
- Route C is powerful but expensive and riskier.
- Route D is right only if mobile delivery is the primary milestone.
- Route E improves product promise but can deepen existing architecture debt.
- Route B allows a practical hybrid: stabilize first, improve architecture where it reduces real risk, and prepare mobile contracts without pausing product momentum.

## Hybrid Patterns Worth Considering

- `A + B`: stabilize quickly, then continue into incremental architecture and UX improvement.
- `A + E`: make current product safer, then complete visible feature gaps.
- `B + D`: balanced modernization with mobile contract work pulled earlier.
- `B + selected C`: incremental improvement plus durable queue/migrations/vector abstraction where most urgent.
- `A + B + selected E`: recommended if a pilot/demo is soon but product completeness matters.
