# LLD Practice Platform

A small end-to-end prototype for practicing Low-Level Design: choose a problem → design →
submit → get feedback (deterministic + LLM) → review → try again.

See also: [`docs/research_note.md`](docs/research_note.md), [`docs/design_note.md`](docs/design_note.md), [`AI_USAGE.md`](AI_USAGE.md).

## Stack
- **Backend**: Python 3 + Flask, SQLite (stdlib `sqlite3`), plain `requests` for the
  Gemini API call (no SDK dependency).
- **Frontend**: vanilla HTML/CSS/JS, no build step, served by Flask itself.
- **Tests**: `unittest` (stdlib).

## Run it

```bash
cd backend
python3 -m venv venv && source venv/bin/activate     # optional but recommended
pip install -r requirements.txt

# Optional: enable the LLM half of feedback. Without this, the app still works
# fully — it falls back to deterministic-only feedback with a note explaining why.
# Get a free key at https://aistudio.google.com/apikey
export GEMINI_API_KEY=AIza...
# export GEMINI_MODEL=gemini-flash-latest   # optional, this is the default

python3 app.py
```

Open **http://127.0.0.1:5050**.

The SQLite file (`backend/data.db`) and the three seed problems (Parking Lot, Elevator
System, Vending Machine) are created automatically on first run.

## Run the tests

```bash
python3 -m unittest discover -s tests -v
```

No network or API key needed — the LLM-dependent path is tested via a fake evaluator that
simulates failure, not a real network call.

## Project layout

```
backend/
  models.py              domain entities: Problem, Attempt, Submission, EvaluationResult
  db.py                  SQLite connection + schema
  repository.py          repositories (domain objects <-> SQL rows)
  evaluators.py          EvaluationStrategy: Deterministic / LLM / Composite
  evaluation_service.py  orchestrates submit -> evaluate, owns the status state machine
  seed_data.py           the 3 seeded problems + their rubrics
  app.py                 Flask routes
frontend/
  index.html, style.css, app.js   single-page app, no build step
tests/
  test_domain.py          state machine, evaluators, repository round-trip
docs/
  research_note.md, design_note.md
AI_USAGE.md
```

## API summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/problems` | list problems |
| GET | `/api/problems/<id>` | problem detail |
| GET | `/api/problems/<id>/attempts` | attempt history for a problem |
| POST | `/api/attempts` | start an attempt `{problem_id}` |
| GET | `/api/attempts/<id>` | attempt detail + latest submission/result |
| POST | `/api/attempts/<id>/submit` | submit `{content, format}` → triggers evaluation |
| POST | `/api/attempts/<id>/retry` | retry evaluation after `evaluation_failed` |

## Known limitations (honest, by design — see scope boundary in the assignment)
- Single implicit learner, no auth/accounts.
- Evaluation is synchronous (fine at this scale; see "What happens when evaluation is slow
  or fails" in `docs/design_note.md` for how this would move to a job queue).
- The deterministic evaluator uses keyword/pattern heuristics, not a real parser/AST — it
  checks *coverage*, not correctness, by design (see design note's trade-offs section).
- No diagram submission format yet, though `SubmissionFormat` is built as an enum specifically
  so adding one doesn't require touching `Attempt`, `EvaluationStrategy`, or the API shape.
- Styling is intentionally minimal — this is a design/evaluation prototype, not a polished
  product.
