# Functional Flows

## Feature Inventory

- Login, register, reset password.
- Authenticated AI tutor chat with streaming answers.
- Knowledge base selection by class, subject, folder, chapter/PDF.
- PDF viewer for selected content.
- File upload for PDFs/images and background indexing.
- Lesson plan generation, lesson cards, card completion.
- Quiz generation/submission and latest quiz/session management.
- Flashcard generation and artifact save/load.
- Summary viewing and saving to notes.
- Notes CRUD.
- Assessment practice quizzes and question papers with attempt recording.
- Progress dashboard, insights, study plan, reminders.
- Preferred language and translation.
- Subscription catalog, quote, activation, plan/usage display.
- Student/mentor/admin role hub.
- Link students, collaboration notes, mentor assignments, reports.
- Admin model profile switching.
- Admin KB reindex.
- PWA install and offline GET/mutation behavior.

## Student Journey: Chat With Selected Chapter

1. User logs in.
2. App bootstraps session and opens workspace.
3. ChatPanel loads class list, sessions, plan summary, and saved context.
4. User selects class -> subject -> folder -> content.
5. Frontend saves `/context` and may save `/sessions/{id}/content`.
6. User asks a question.
7. WebSocket `/ws/ask` streams status/chunks/end.
8. Backend retrieves selected PDF/upload context, generates grounded answer, saves chat.
9. Frontend appends assistant message and keeps session in localStorage/session list.

Potential gaps:

- Empty selected content or stale content id can create confusing "no context" behavior.
- WebSocket frame schema is informal; richer error display depends on string parsing.

## Student Journey: Upload Personal Material

1. User chooses class/subject/folder/display name and file.
2. `POST /files/upload` stores file under user upload root.
3. Backend creates indexing job.
4. UI polls `/files/index-status?file_id=...`.
5. After indexed, uploaded content appears in tree/selectors.
6. User asks questions or generates lessons/quizzes against that file.

Potential gaps:

- Indexing is background but not externally durable beyond recovery.
- If OCR/Tesseract is unavailable, image learning quality falls sharply.
- UI needs clear failure recovery for `index_failed`.

## Student Journey: Lesson Plan

1. User selects content/context.
2. Opens Lesson panel.
3. Clicks generate/regenerate.
4. Backend retrieves chapter context, asks model, normalizes/falls back, persists plan/cards.
5. UI displays steps/cards.
6. User completes cards.
7. User can generate quiz/flashcards for a specific card.

Potential gaps:

- Lesson quality depends on model JSON/list compliance.
- The distinction between lesson steps and lesson cards may be unclear to users.

## Student Journey: Quiz

1. User selects context or active lesson card.
2. Generates quiz.
3. Backend retrieves content, creates/normalizes questions, persists quiz.
4. User answers and submits.
5. Backend scores answers and stores results.
6. Progress/analytics can use quiz activity.

Potential gaps:

- Generated quiz correctness needs stronger validation/citations.
- Answer submission is session/quiz id sensitive; stale localStorage ids can confuse.

## Student Journey: Flashcards

1. User selects lesson card/content.
2. Generates flashcards.
3. Backend extracts/retrieves text and generates cards.
4. UI displays deck.
5. User can save artifact metadata.

Potential gaps:

- Two paths exist: `/flashcards/` router and card artifact generation.
- Need unified "saved deck" user journey.

## Student Journey: Notes

1. User views/generated summary or opens Notes panel.
2. Saves note with content/title.
3. Notes list refreshes.
4. User edits/deletes notes.

Potential gaps:

- Editor serializes markdown/html-ish content; formatting fidelity may drift.
- Sanitization/accessibility review needed.

## Student Journey: Progress

1. User opens Progress panel.
2. Frontend fetches dashboard, insights, study plan, preferences.
3. User updates reminder settings or study plan item state.
4. Assignments can be filtered and updated.

Potential gaps:

- Study plan sources are mixed: activity, assignments, assessments.
- Some date parsing is label-based, so edge cases may mis-sort.

## Mentor/Parent/Teacher Journey

1. Mentor logs in.
2. Links a student by email.
3. Views roster and selected student progress.
4. Adds collaboration notes.
5. Creates/updates/deletes assignments.
6. Exports/prints reports.

Potential gaps:

- Relationship invitation/approval flow is not visible; linking appears direct.
- Assignment templates are localStorage-only.

## Admin Journey

1. Admin logs in.
2. Opens admin/role hub.
3. Switches global model profile.
4. Starts full/incremental KB reindex and watches status.
5. Can inspect broader uploaded file trees/status.

Potential gaps:

- Admin reindex is in-process and can be expensive.
- No multi-admin audit trail for model profile changes beyond `updated_by` field.

## Missing or Broken UX Paths

- No URL routing/deep links to a specific panel/session.
- Session expiry during long WebSocket generation may produce partial assistant text plus logout.
- Offline mutation replay has no user-level conflict resolution.
- Upload/index failures need more actionable repair steps.
- Role-based empty states need careful review for teacher/parent/admin first-run.
- Mobile navigation is likely cramped because ChatPanel/RoleHub are desktop-workspace oriented.
