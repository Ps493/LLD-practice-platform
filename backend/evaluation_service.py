"""Orchestrates the practice loop's submit -> evaluate step and owns the
attempt status transitions. Kept separate from the Flask route handlers so
it's testable without an HTTP layer (see tests/test_domain.py)."""

from __future__ import annotations

from models import Attempt, AttemptStatus, Problem, Submission
from repository import AttemptRepository, EvaluationResultRepository
from evaluators import CompositeEvaluator, EvaluationStrategy


class EvaluationService:
    def __init__(
        self,
        attempt_repo: AttemptRepository,
        result_repo: EvaluationResultRepository,
        evaluator: EvaluationStrategy | None = None,
    ):
        self.attempt_repo = attempt_repo
        self.result_repo = result_repo
        self.evaluator = evaluator or CompositeEvaluator()

    def run(self, attempt: Attempt, problem: Problem, submission: Submission):
        """Moves an attempt SUBMITTED -> EVALUATING -> EVALUATED|EVALUATION_FAILED.

        Synchronous for this prototype (evaluation is fast enough not to need
        a queue at this scale). Any unexpected exception still leaves the
        attempt in a terminal, retryable state rather than stuck EVALUATING.
        """
        attempt.transition_to(AttemptStatus.EVALUATING)
        self.attempt_repo.update_status(attempt.id, attempt.status)

        try:
            result = self.evaluator.evaluate(problem, submission)
            self.result_repo.add(result)
            attempt.transition_to(AttemptStatus.EVALUATED)
            self.attempt_repo.update_status(attempt.id, attempt.status)
            return result
        except Exception:
            attempt.transition_to(AttemptStatus.EVALUATION_FAILED)
            self.attempt_repo.update_status(attempt.id, attempt.status)
            raise
