# Design Note

## MVP scope
Three seeded problems (Parking Lot, Elevator System, Vending Machine), a single learner
(no auth — out of scope for 2 days), one submission format at a time (text design or code
skeletons), synchronous evaluation, SQLite persistence, a small vanilla-JS frontend, a Flask
JSON API. No LMS features (courses, cohorts, grading dashboards) — the assignment explicitly
scopes those out, and they don't change the answer to "is this design good."

## User flow
```
Problem list → Problem detail (requirements + history) → Start attempt
   → Design screen (pick format, write, submit)
   → Feedback screen (score, strengths, issues, suggestions, source, notes)
   → "Try again" (new attempt, same problem) or back to history
```
Attempt status is shown at every step (`draft → submitted → evaluating → evaluated` or
`evaluation_failed`, with a retry action) so the learner always knows what state their work
is in — this doubles as the answer to "what if evaluation fails."

## Important classes / interfaces
- **`Problem`** — id, requirements, `core_entities` (used by the deterministic evaluator),
  `rubric` (used by the LLM evaluator). Both evaluators are grounded in the *same* problem
  definition so their feedback doesn't diverge from different sources of truth.
- **`Attempt`** — owns an explicit `AttemptStatus` state machine
  (`DRAFT → SUBMITTED → EVALUATING → EVALUATED | EVALUATION_FAILED → EVALUATING`), with
  `transition_to()` raising `IllegalStatusTransition` on an illegal move (e.g. evaluating a
  draft, or resubmitting an already-evaluated attempt — see `tests/test_domain.py`). This was
  a deliberate choice over a free-text status string: it makes "what states are even
  possible" part of the code, not the docs.
- **`Submission`** — content + a `SubmissionFormat` enum (`TEXT_DESIGN`, `CODE` today).
- **`EvaluationStrategy`** (ABC) — the extensibility seam. `DeterministicEvaluator` and
  `LLMEvaluator` both implement `evaluate(problem, submission) -> EvaluationResult`;
  `CompositeEvaluator` composes them. Swapping evaluation approach or adding a third strategy
  (e.g. a static-analysis evaluator for real code, or a second "critic" LLM pass) means adding
  one class, not touching the service or API layer.
- **`EvaluationService`** — the only thing that knows how `Attempt` status should move during
  evaluation; keeps that logic out of the Flask route handlers so it's unit-testable without
  HTTP (see `tests/test_domain.py`).
- **Repositories** (`ProblemRepository`, `AttemptRepository`, `SubmissionRepository`,
  `EvaluationResultRepository`) — the only code that knows SQLite exists. Domain classes are
  plain dataclasses with no persistence awareness.

## Evaluation approach: what's deterministic vs. what needs an LLM
| Concern | Deterministic | LLM |
|---|---|---|
| Did the attempt mention the problem's core entities? | ✅ fast, reproducible | — |
| Are relationships (inheritance/composition/interfaces) expressed, not just a flat list? | ✅ pattern/keyword signals | — |
| Are edge cases / failure modes addressed? | ✅ keyword signals | ✅ can judge if they're the *right* edge cases |
| Is a class doing too much (poor cohesion)? | ❌ can't judge | ✅ |
| Does the chosen pattern actually fit the problem? | ❌ can't judge | ✅ |
| Is the trade-off reasoning sound? | ❌ can't judge | ✅ |

The deterministic pass answers "did you engage with the problem's known shape," which is
necessary but not sufficient for a good design — hence the explicit rubric statement
("more than one valid design exists — do not penalize a reasonable alternative to the
expected entities") in the LLM prompt, so it grades *design quality*, not "did you use my
exact class names."

## Handling multiple valid solutions
Two mechanisms: (1) the deterministic evaluator only ever produces *coverage* signals and
issues, never "this is wrong" — missing an expected entity is flagged as a gap to consider,
not an error; (2) the LLM prompt is explicitly instructed not to penalize a reasonable
alternative design. Score is a signal to act on, not a verdict.

## What happens when evaluation is slow or fails
For this prototype, evaluation runs synchronously with a 20s timeout on the LLM call. Any
`LLMEvaluatorError` (missing key, network error, bad JSON) is caught inside
`CompositeEvaluator`, which returns the deterministic result plus a `notes` field explaining
what's missing — the learner is never blocked on the LLM and never sees a raw error. If the
*deterministic* pass itself somehow throws (it shouldn't — it's pure string logic), the
`Attempt` is moved to `EVALUATION_FAILED` (not left stuck `EVALUATING`) and the API exposes a
`POST /attempts/<id>/retry` endpoint the frontend surfaces as a "Retry evaluation" button, re-
using the already-saved submission.

**If this needed to scale** (slow AI evaluation, many concurrent learners): move the LLM call
out of the request/response cycle — `submit` would enqueue a job (e.g. RQ/Celery + Redis),
return `202 EVALUATING` immediately, and the frontend would poll `GET /attempts/<id>` (already
supported) until status flips to `EVALUATED`/`EVALUATION_FAILED`. No domain model change is
needed for this — `AttemptStatus.EVALUATING` already exists for exactly this purpose; only the
service's `run()` method would move from an inline call to a job dispatch, and `app.py` would
stop waiting on it synchronously. This is intentionally *not* built now, per the scope
boundary (no distributed-systems rabbit hole for a synchronous, low-QPS prototype).

## Key trade-offs
- **SQLite over Postgres**: zero setup for a 2-day prototype; `db.py` isolates all SQL so
  swapping is a single-file change.
- **Synchronous evaluation over a job queue**: simpler to demo end-to-end in the time box;
  the state machine is already shaped for an async version (see above).
- **No auth / single implicit learner**: out of scope per the assignment's focus on the
  learner journey, not a multi-tenant system.
- **Keyword/pattern heuristics for the deterministic evaluator, not an AST parser**: the
  submission format is free text or pseudocode, not guaranteed-valid code in one language, so
  a real parser would either reject valid pseudocode or need per-language support neither the
  timebox nor the problem statement calls for.
