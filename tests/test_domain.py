"""
Run with: python3 -m unittest discover -s tests -v
(from the backend/ directory added to PYTHONPATH — see README)

Covers the important behaviour + failure/edge cases the assignment asks for:
- Attempt status state machine (legal + illegal transitions)
- DeterministicEvaluator scoring on a strong vs weak submission
- CompositeEvaluator's graceful degradation when the LLM call fails
- Repository round-trips (SQLite in a temp file)
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from models import (  # noqa: E402
    Attempt, AttemptStatus, IllegalStatusTransition, Problem, Submission,
    SubmissionFormat, new_id,
)
from evaluators import DeterministicEvaluator, CompositeEvaluator, LLMEvaluator, LLMEvaluatorError  # noqa: E402


SAMPLE_PROBLEM = Problem(
    id="p1", title="Parking Lot", difficulty="Medium", summary="...",
    requirements=["r1"],
    core_entities=["ParkingLot", "ParkingSpot", "Vehicle", "Ticket"],
    rubric=["rubric1"],
)


class TestAttemptStateMachine(unittest.TestCase):
    def test_legal_transition_sequence(self):
        a = Attempt(id=new_id(), problem_id="p1")
        self.assertEqual(a.status, AttemptStatus.DRAFT)
        a.transition_to(AttemptStatus.SUBMITTED)
        a.transition_to(AttemptStatus.EVALUATING)
        a.transition_to(AttemptStatus.EVALUATED)
        self.assertEqual(a.status, AttemptStatus.EVALUATED)

    def test_illegal_transition_raises(self):
        a = Attempt(id=new_id(), problem_id="p1")
        with self.assertRaises(IllegalStatusTransition):
            a.transition_to(AttemptStatus.EVALUATING)  # can't skip SUBMITTED

    def test_evaluation_failed_is_retryable(self):
        a = Attempt(id=new_id(), problem_id="p1", status=AttemptStatus.SUBMITTED)
        a.transition_to(AttemptStatus.EVALUATING)
        a.transition_to(AttemptStatus.EVALUATION_FAILED)
        a.transition_to(AttemptStatus.EVALUATING)  # retry is legal
        self.assertEqual(a.status, AttemptStatus.EVALUATING)

    def test_evaluated_is_terminal(self):
        a = Attempt(id=new_id(), problem_id="p1", status=AttemptStatus.EVALUATED)
        with self.assertRaises(IllegalStatusTransition):
            a.transition_to(AttemptStatus.SUBMITTED)


class TestDeterministicEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = DeterministicEvaluator()

    def test_strong_submission_scores_high(self):
        submission = Submission(
            id=new_id(), attempt_id="a1", format=SubmissionFormat.TEXT_DESIGN,
            content=(
                "class ParkingLot has many ParkingSpot via composition. "
                "abstract class Vehicle extends to Car, Bus. class Ticket. "
                "interface PaymentStrategy allows extensibility. "
                "Edge case: if lot is full, reject entry."
            ),
        )
        result = self.evaluator.evaluate(SAMPLE_PROBLEM, submission)
        self.assertGreaterEqual(result.score, 70)
        self.assertEqual(result.source, "deterministic")
        self.assertTrue(any("ParkingLot" in s for s in result.strengths))

    def test_weak_submission_scores_low_and_lists_missing_entities(self):
        submission = Submission(
            id=new_id(), attempt_id="a1", format=SubmissionFormat.TEXT_DESIGN,
            content="it's basically a big array and a loop",
        )
        result = self.evaluator.evaluate(SAMPLE_PROBLEM, submission)
        self.assertLess(result.score, 40)
        self.assertTrue(any("ParkingLot" in i for i in result.issues))

    def test_empty_core_entities_does_not_divide_by_zero(self):
        problem = Problem(id="p2", title="X", difficulty="Easy", summary="",
                           requirements=[], core_entities=[], rubric=[])
        submission = Submission(id=new_id(), attempt_id="a1",
                                 format=SubmissionFormat.TEXT_DESIGN, content="anything")
        result = self.evaluator.evaluate(problem, submission)  # should not raise
        self.assertIsInstance(result.score, int)


class _AlwaysFailingLLM(LLMEvaluator):
    def evaluate(self, problem, submission):
        raise LLMEvaluatorError("simulated network failure")


class TestCompositeEvaluatorDegradesGracefully(unittest.TestCase):
    def test_falls_back_to_deterministic_on_llm_failure(self):
        composite = CompositeEvaluator(llm_evaluator=_AlwaysFailingLLM())
        submission = Submission(
            id=new_id(), attempt_id="a1", format=SubmissionFormat.TEXT_DESIGN,
            content="class ParkingLot has ParkingSpot. class Vehicle. class Ticket.",
        )
        result = composite.evaluate(SAMPLE_PROBLEM, submission)
        self.assertEqual(result.source, "composite")
        self.assertIn("unavailable", result.notes)
        self.assertIsNotNone(result.score)  # learner still gets a usable result


class TestRepositoryRoundTrip(unittest.TestCase):
    def setUp(self):
        import db as db_module
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_module.DB_PATH = self._tmp.name
        db_module.init_db()

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_problem_and_attempt_round_trip(self):
        from repository import ProblemRepository, AttemptRepository
        problem_repo = ProblemRepository()
        attempt_repo = AttemptRepository()

        problem_repo.add(SAMPLE_PROBLEM)
        fetched = problem_repo.get("p1")
        self.assertEqual(fetched.title, "Parking Lot")
        self.assertEqual(fetched.core_entities, ["ParkingLot", "ParkingSpot", "Vehicle", "Ticket"])

        attempt = Attempt(id=new_id(), problem_id="p1")
        attempt_repo.add(attempt)
        attempt_repo.update_status(attempt.id, AttemptStatus.SUBMITTED)
        fetched_attempt = attempt_repo.get(attempt.id)
        self.assertEqual(fetched_attempt.status, AttemptStatus.SUBMITTED)


if __name__ == "__main__":
    unittest.main()
