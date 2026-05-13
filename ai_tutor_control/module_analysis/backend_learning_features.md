# Module Analysis: Backend Learning Features

## `modules/history.py`

- Purpose: persist and fetch chat history by user/session.
- Inputs: user id, session id, question, answer, selected content metadata.
- Outputs: rows in `chat_history`, session lists/history payloads.
- Interactions: RAG saves chats; `/history` and `/sessions` read via routes/services.
- Risks: session metadata is stored on chat rows, so empty sessions do not exist until first message/content save.
- Tests: e2e, session CRUD, learning-session service tests.

## `modules/lesson_plan.py`

- Purpose: create and manage lesson plans, adaptive steps, normalized lesson cards, card progress.
- Inputs: subject/chapter/session/content refs, user id, model output, card ids.
- Outputs: `lesson_plans`, `lesson_cards`, `lesson_card_progress`, lesson steps/cards.
- Internal logic:
  - Retrieves content with `retrieve_chunks`.
  - Generates plan with LLM and parses JSON/list-like output.
  - Falls back to default/adaptive content-derived steps.
  - Rewrites overly extractive content.
  - Saves card records and supports completion/next-step APIs.
- Dependencies: DB, file management, RAG retrieval, model manager, quiz helpers.
- Risks:
  - Heavy parsing/fallback logic in one file.
  - LLM output variability drives complexity.
  - Lesson cards depend on plan shape; schema changes affect quiz/flashcard card generation.
- Tests: `test_lesson_plan.py`, e2e, lesson frontend flow.

## `modules/quiz.py`

- Purpose: generate, persist, retrieve, submit, and manage quizzes.
- Inputs: subject/chapter/session/content/card context, model output, submitted answers.
- Outputs: quiz JSON, `lesson_quizzes`, `lesson_quiz_results`, scoring feedback.
- Internal logic:
  - Retrieves context and asks model for MCQs.
  - Extracts/normalizes JSON, labels/options, and answers.
  - Builds grounded fallback questions from context when needed.
  - Persists sessions and answers.
- Risks:
  - JSON extraction from LLM text is fragile.
  - Answer normalization must handle labels and free text.
- Tests: quiz, e2e, frontend quiz flow.

## `modules/flashcards.py`

- Purpose: generate flashcards from files/content.
- Inputs: file paths or selected content, count, user/session.
- Outputs: flashcard items and learning artifact rows.
- Internal logic:
  - Resolves files, extracts text, prompts model, normalizes card data.
  - Also exposes an APIRouter mounted under `/flashcards`.
- Risks:
  - Router lives in feature module while most API routes live in `routes.py`.
  - File extraction can be expensive synchronously.
- Tests: flashcard paths covered in feature/e2e/unit panels.

## `modules/artifacts.py`

- Purpose: store generated learning artifacts, especially card-level quizzes/flashcards.
- Inputs: lesson card id, artifact type, model output, save metadata.
- Outputs: `learning_artifacts` rows and artifact DTOs.
- Interactions: Lesson/Quiz/Flashcard panels generate card artifacts; notes/summary flows can save derived content.
- Risks: `meta_json` is flexible but weakly typed.
- Tests: covered via lesson/quiz/flashcard tests.

## `modules/assessment.py`

- Purpose: assessment generator and attempt tracking.
- Inputs: subject/chapter/difficulty/question count/duration/marks.
- Outputs: subject quizzes/question papers, persisted papers, attempt summaries.
- Internal logic:
  - Retrieves subject context.
  - Generates MCQs or question paper content.
  - Builds fallback MCQs.
  - Persists papers and records attempts.
- Risks: generated assessment validity depends on context quality and model compliance.
- Tests: `test_assessment_features.py`, progress analytics.

## `modules/notes.py`

- Purpose: saved summary notes CRUD.
- Inputs: title/content/payload.
- Outputs: note DTOs and DB rows.
- Internal logic:
  - Derives title if missing.
  - Serializes payload JSON.
  - Restricts operations by user id.
- Risks: content is stored as raw markdown/html-ish text from frontend editor; sanitization is mostly frontend/rendering-dependent.
- Tests: summary notes API and UI tests.

## `modules/progress.py`

- Purpose: simple lesson step progress helper.
- Inputs: user/session/step/status.
- Outputs: progress rows and completed ids.
- Risks: overlaps with richer `analytics.py` and lesson card progress.
- Tests: lesson/progress tests.
