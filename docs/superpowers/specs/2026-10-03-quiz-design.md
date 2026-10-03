# Quiz + coin rewards — backend design

Status: design approved by user; pending written-spec review.

Wire contract (owned by the FE repo, already agreed): `FoodFenFE/docs/backend-contracts/quiz.md`.
This spec covers only how the backend implements it. A shape change starts in that contract file.

## Goal

Nutrition quizzes that pay coins through the existing ledger. The client never reports a score:
it submits chosen options, the server grades and pays. Correct answers exist only server-side and
appear only in the `submit` / completed-quiz response.

## Decisions

| Topic | Decision |
|---|---|
| Content language | Vietnamese only. No `language` param. |
| Rewards | Daily 4 coins/correct, practice 1 coin/correct, practice cap 10 coins per `quiz_date`. |
| Where rewards live | `settings` (env-overridable), passed into use cases by DI like `CreateCheckoutUseCase`'s prices. Changing them needs a restart, not a code change. |
| Question selection | 5 random active questions, preferring ones the user has not seen; fall back to seen ones when the pool runs out. Daily draws from all topics, practice from the chosen topic. |
| Question bank | DB tables, seeded by migration (`0017`), edited later with SQL. |
| Seed content | Drafted by Claude in Vietnamese, reviewed by the repo owner before merge. Needs a real nutrition review. |

## Data

New tables (UUID PKs, registered in `db/models/__init__.py`):

- `quiz_topics(id, slug unique, label, active)`. The API exposes `slug` as the topic `id`.
- `quiz_questions(id, topic_id FK, text, options JSON [{id,text}], correct_option_id, explanation, active)`.
  Options are never queried individually, so no `quiz_options` table.
- `quizzes(id, user_id, kind, topic_id null, quiz_date, question_ids JSON, answers JSON null,
  correct_count null, coins_earned null, submitted_at null, created_at)`.
  - Partial unique index on `(user_id, quiz_date) WHERE kind = 'daily'`.
  - `kind` is `QuizKind` (`daily`, `practice`) in `domain/enums.py`, mapped with `enum_column()`.

`CoinReason` gains `QUIZ_DAILY` and `QUIZ_PRACTICE`. The migration drops and recreates the
`coin_reason` CHECK using the bare name (see migration 0008).

Migrations: `0016` structure + CoinReason, `0017` seed content (separate so it reviews alone).

## Behaviour

- `GET /quizzes/topics` — active topics.
- `GET /quizzes/daily?date=` — validate `date` is within ±1 day of server UTC today (else 400).
  Create lazily with `INSERT … ON CONFLICT DO NOTHING` on the partial unique index, then read.
- `POST /quizzes/practice {topic, date}` — same date check; unknown topic 404; always inserts a new row.
- `GET /quizzes/{id}` — own quizzes only; a missing id and another user's id are both 404.
  `status`/`result` come from `submitted_at`/`answers`. The Quiz payload never contains a correct option.
- `POST /quizzes/{id}/submit` — see below.

`coinsPerCorrect` is the kind's per-correct reward. `coinsRemainingToday` is `cap − used` for
practice (used = sum of `coins_earned` of submitted practice quizzes with the same `quiz_date`),
`null` for daily.

### Submit

1. Load the quiz (404 rule above). Require exactly one answer per question, each `optionId` valid
   for its question, else 400.
2. For practice: lock the user row (`coins.balance(for_update=True)`), then compute `used`.
3. `earned = correct × coinsPerCorrect`; for practice `earned = min(earned, cap − used)`.
4. `UPDATE quizzes SET answers, correct_count, coins_earned, submitted_at WHERE id=? AND user_id=?
   AND submitted_at IS NULL`. Zero rows changed → 409 `quiz_already_submitted`. Only the request that
   flips `submitted_at` writes to the ledger, so a retry or race cannot pay twice; this is the
   per-user+quiz guard the contract asks for.
5. If `earned > 0`, add one ledger row with `QUIZ_DAILY` / `QUIZ_PRACTICE`. A quiz that earns 0
   writes no ledger row.
6. Return `QuizResult` with the new `balance`.

## Errors

The existing handlers return `{"message": …}` only, so `quiz_already_submitted` needs its own
handler (like `UserAlreadyExistsException`) returning 409 with `{"message", "error": "quiz_already_submitted"}`.
New exceptions: quiz-not-found (`EntityNotFoundException` subclass → 404), already-submitted (409,
own handler), invalid answers and out-of-window date (`InvalidAttributeException` subclass → 400).
Schema-level problems (e.g. a malformed `date`) stay 422 under the repo's existing validation handler.

## Layers

- `domain/`: `Quiz`, `QuizQuestion`, `QuizTopic` entities (invariants in `__post_init__`/factory:
  5 questions, distinct), exceptions.
- `application/`: `QuizRepositoryProtocol` port, dataclass DTOs, use cases `ListQuizTopics`,
  `GetDailyQuiz`, `StartPracticeQuiz`, `GetQuiz`, `SubmitQuiz`.
- `infrastructure/`: ORM models, `SQLAlchemyQuizRepository`, providers in `di/use_cases.py` and
  `di/repositories.py`.
- `adapters/`: `quiz_controller.py`, camelCase schemas.

## Testing

Unit: grading, cap arithmetic, selection preferring unseen. API (SQLite): payload never exposes a
correct option; second submit → 409 with the error code; practice past cap → 200 with
`coinsEarned: 0`; date outside ±1 day → 400; another user's quiz → 404; incomplete answers → 400.
Not covered: concurrent submits, because SQLite ignores `FOR UPDATE` (same as coin redeem today).

## Out of scope

Admin endpoints, per-user personalization/RAG, a quest tied to the quiz, a quiz history list,
English content.
