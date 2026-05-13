# UI/UX Review

## Overall UX

The product is a dense learning workspace rather than a landing-page app. That matches the domain, but the central workspace has grown broad enough that navigation, state clarity, and mobile responsiveness are the main UX risks.

## Strengths

- Authenticated workspace exposes practical learning tools immediately.
- Knowledge selection, chat, lessons, quizzes, flashcards, notes, progress, and role tools are connected.
- PWA/offline status and backend health indicators are thoughtful.
- Visual regression tests exist for key screens.
- Markdown answer rendering supports rich educational responses.

## Main UX Issues

- `ChatPanel` owns too many workflows, making transitions and empty/loading/error states hard to keep consistent.
- RoleHub combines mentor, parent/teacher, admin, assignments, templates, notes, reports, and model profile controls.
- There is no route-level navigation or browser history for panels.
- Selected context may be unclear after switching sessions/panels.
- Upload indexing state is asynchronous but likely needs clearer progress, failed state, retry, and "ready to ask" affordances.
- Chat streaming errors are text tokens inside the conversation, which can feel like assistant content.
- Offline queued mutations need a review/resolve surface, not only a pending count.

## Accessibility Gaps

- Need systematic keyboard navigation review for workspace sidebar, panel tabs, PDF viewer resize, note editor, dropdowns, assignment templates.
- Voice input needs clear unsupported-browser state and permission-denied handling.
- Rich note editor should expose labels/roles and predictable shortcuts.
- Color contrast and focus outlines need audit in `components/style.css` and `index.css`.
- Markdown-rendered content needs accessible table/code/list styling.

## Responsiveness Concerns

- Workspace/sidebar/viewer composition is desktop-first.
- Chat + PDF split viewer + side panels will be hard on mobile.
- RoleHub and ProgressPanel have dense filter/report controls that likely overflow on small screens.
- Large fixed/complex panels need mobile-specific stacked layouts and bottom navigation.

## Performance Concerns

- Large components may rerender heavily during streaming.
- Markdown rendering on every token can become expensive if not batched.
- Huge CSS file may increase style recalculation complexity.
- LocalStorage operations for queues/templates/context occur in UI flows.
- Visual PDF loading plus chat streaming can strain lower-end devices.

## Actionable Improvements

1. Split workspace into explicit panel modules with a small central state reducer.
2. Add route-like navigation state (`/workspace/chat`, `/workspace/lesson`, etc.) even if still SPA-only.
3. Build a single `LearningContextBar` that always shows selected class/subject/content/index status.
4. Move upload/indexing into a dedicated drawer or panel with clear states: queued, indexing, ready, failed, retry.
5. Use structured toast/banner errors for WebSocket/API failures instead of only chat text.
6. Extract shared assignment/date/filter utilities.
7. Add keyboard/focus tests for core panels.
8. Add mobile breakpoints for sidebar collapse, bottom tabs, full-screen viewer, and stacked panel content.
9. Virtualize long chat/history/assignment lists if they grow.
10. Define component-level CSS ownership or CSS modules to reduce global style coupling.
