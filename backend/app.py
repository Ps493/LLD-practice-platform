"""
Flask API for the LLD Practice Platform.

Routes map directly onto the practice loop:
  GET  /api/problems               -> choose problem
  GET  /api/problems/<id>          -> problem detail
  POST /api/attempts               -> start an attempt (think/design)
  POST /api/attempts/<id>/submit   -> submit -> triggers evaluation
  POST /api/attempts/<id>/retry    -> retry evaluation after a failure
  GET  /api/attempts/<id>          -> attempt detail + latest result (review)
  GET  /api/problems/<id>/attempts -> history (try again / review)
"""

from __future__ import annotations

from flask import Flask, jsonify, request, send_from_directory
from pathlib import Path

from db import init_db
from models import Attempt, AttemptStatus, Submission, SubmissionFormat, new_id, IllegalStatusTransition
from repository import ProblemRepository, AttemptRepository, SubmissionRepository, EvaluationResultRepository
from evaluation_service import EvaluationService
from seed_data import PROBLEMS

app = Flask(__name__, static_folder=None)

problem_repo = ProblemRepository()
attempt_repo = AttemptRepository()
submission_repo = SubmissionRepository()
result_repo = EvaluationResultRepository()
evaluation_service = EvaluationService(attempt_repo, result_repo)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


def bootstrap():
    init_db()
    if not problem_repo.list_all():
        for p in PROBLEMS:
            problem_repo.add(p)


# ---------- static frontend ----------

@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:filename>")
def static_files(filename):
    if (FRONTEND_DIR / filename).exists():
        return send_from_directory(FRONTEND_DIR, filename)
    return jsonify({"error": "not found"}), 404


# ---------- problems ----------

@app.get("/api/problems")
def list_problems():
    problems = problem_repo.list_all()
    return jsonify([
        {"id": p.id, "title": p.title, "difficulty": p.difficulty, "summary": p.summary, "tags": p.tags}
        for p in problems
    ])


@app.get("/api/problems/<problem_id>")
def get_problem(problem_id):
    p = problem_repo.get(problem_id)
    if not p:
        return jsonify({"error": "problem not found"}), 404
    return jsonify({
        "id": p.id, "title": p.title, "difficulty": p.difficulty, "summary": p.summary,
        "requirements": p.requirements, "tags": p.tags,
    })


@app.get("/api/problems/<problem_id>/attempts")
def problem_history(problem_id):
    attempts = attempt_repo.list_for_problem(problem_id)
    out = []
    for a in attempts:
        latest_sub = submission_repo.latest_for_attempt(a.id)
        latest_result = result_repo.for_submission(latest_sub.id)[-1:] if latest_sub else []
        out.append({
            "id": a.id, "status": a.status.value, "created_at": a.created_at,
            "updated_at": a.updated_at,
            "score": latest_result[0].score if latest_result else None,
        })
    return jsonify(out)


# ---------- attempts ----------

@app.post("/api/attempts")
def start_attempt():
    body = request.get_json(force=True) or {}
    problem_id = body.get("problem_id")
    if not problem_repo.get(problem_id):
        return jsonify({"error": "unknown problem_id"}), 400

    attempt = Attempt(id=new_id(), problem_id=problem_id, status=AttemptStatus.DRAFT)
    attempt_repo.add(attempt)
    return jsonify(_attempt_json(attempt)), 201


@app.get("/api/attempts/<attempt_id>")
def get_attempt(attempt_id):
    a = attempt_repo.get(attempt_id)
    if not a:
        return jsonify({"error": "attempt not found"}), 404

    submission = submission_repo.latest_for_attempt(attempt_id)
    result = None
    if submission:
        results = result_repo.for_submission(submission.id)
        if results:
            r = results[-1]
            result = {
                "score": r.score, "strengths": r.strengths, "issues": r.issues,
                "suggestions": r.suggestions, "notes": r.notes, "source": r.source,
            }

    return jsonify({
        **_attempt_json(a),
        "submission": {"format": submission.format.value, "content": submission.content} if submission else None,
        "result": result,
    })


@app.post("/api/attempts/<attempt_id>/submit")
def submit_attempt(attempt_id):
    attempt = attempt_repo.get(attempt_id)
    if not attempt:
        return jsonify({"error": "attempt not found"}), 404

    body = request.get_json(force=True) or {}
    content = (body.get("content") or "").strip()
    fmt = body.get("format", "text_design")
    if not content:
        return jsonify({"error": "content is required"}), 400
    if fmt not in [f.value for f in SubmissionFormat]:
        return jsonify({"error": f"unsupported format: {fmt}"}), 400

    submission = Submission(id=new_id(), attempt_id=attempt_id, format=SubmissionFormat(fmt), content=content)
    submission_repo.add(submission)

    try:
        attempt.transition_to(AttemptStatus.SUBMITTED)
    except IllegalStatusTransition as e:
        return jsonify({"error": str(e)}), 409
    attempt_repo.update_status(attempt_id, attempt.status)

    problem = problem_repo.get(attempt.problem_id)
    try:
        result = evaluation_service.run(attempt, problem, submission)
    except Exception as e:
        # Evaluation failed end-to-end (should be rare: CompositeEvaluator already
        # degrades gracefully for LLM failures). Attempt is left EVALUATION_FAILED
        # and retryable rather than losing the learner's submission.
        return jsonify({"error": f"evaluation failed: {e}", "attempt": _attempt_json(attempt)}), 502

    return jsonify({
        "attempt": _attempt_json(attempt),
        "result": {
            "score": result.score, "strengths": result.strengths, "issues": result.issues,
            "suggestions": result.suggestions, "notes": result.notes, "source": result.source,
        },
    })


@app.post("/api/attempts/<attempt_id>/retry")
def retry_attempt(attempt_id):
    attempt = attempt_repo.get(attempt_id)
    if not attempt:
        return jsonify({"error": "attempt not found"}), 404
    if attempt.status != AttemptStatus.EVALUATION_FAILED:
        return jsonify({"error": f"attempt is {attempt.status.value}, not retryable"}), 409

    submission = submission_repo.latest_for_attempt(attempt_id)
    problem = problem_repo.get(attempt.problem_id)
    attempt.status = AttemptStatus.SUBMITTED  # legal predecessor to EVALUATING
    try:
        result = evaluation_service.run(attempt, problem, submission)
    except Exception as e:
        return jsonify({"error": f"evaluation failed: {e}", "attempt": _attempt_json(attempt)}), 502

    return jsonify({
        "attempt": _attempt_json(attempt),
        "result": {
            "score": result.score, "strengths": result.strengths, "issues": result.issues,
            "suggestions": result.suggestions, "notes": result.notes, "source": result.source,
        },
    })


def _attempt_json(a: Attempt) -> dict:
    return {
        "id": a.id, "problem_id": a.problem_id, "status": a.status.value,
        "created_at": a.created_at, "updated_at": a.updated_at,
    }


bootstrap()

if __name__ == "__main__":
    app.run(debug=True, port=5050)
