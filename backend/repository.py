from __future__ import annotations

from typing import Optional

from db import get_conn, dumps, loads
from models import (
    Problem, Attempt, Submission, EvaluationResult,
    AttemptStatus, SubmissionFormat,
)


class ProblemRepository:
    def add(self, p: Problem) -> None:
        with get_conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO problems VALUES (?,?,?,?,?,?,?,?)",
                (p.id, p.title, p.difficulty, p.summary,
                 dumps(p.requirements), dumps(p.core_entities), dumps(p.rubric), dumps(p.tags)),
            )

    def get(self, problem_id: str) -> Optional[Problem]:
        with get_conn() as c:
            row = c.execute("SELECT * FROM problems WHERE id=?", (problem_id,)).fetchone()
            return self._row_to_problem(row) if row else None

    def list_all(self) -> list[Problem]:
        with get_conn() as c:
            rows = c.execute("SELECT * FROM problems").fetchall()
            return [self._row_to_problem(r) for r in rows]

    @staticmethod
    def _row_to_problem(row) -> Problem:
        return Problem(
            id=row["id"], title=row["title"], difficulty=row["difficulty"],
            summary=row["summary"], requirements=loads(row["requirements"], []),
            core_entities=loads(row["core_entities"], []), rubric=loads(row["rubric"], []),
            tags=loads(row["tags"], []),
        )


class AttemptRepository:
    def add(self, a: Attempt) -> None:
        with get_conn() as c:
            c.execute(
                "INSERT INTO attempts VALUES (?,?,?,?,?)",
                (a.id, a.problem_id, a.status.value, a.created_at, a.updated_at),
            )

    def update_status(self, attempt_id: str, status: AttemptStatus) -> None:
        with get_conn() as c:
            from models import now_iso
            c.execute(
                "UPDATE attempts SET status=?, updated_at=? WHERE id=?",
                (status.value, now_iso(), attempt_id),
            )

    def get(self, attempt_id: str) -> Optional[Attempt]:
        with get_conn() as c:
            row = c.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone()
            return self._row_to_attempt(row) if row else None

    def list_for_problem(self, problem_id: str) -> list[Attempt]:
        with get_conn() as c:
            rows = c.execute(
                "SELECT * FROM attempts WHERE problem_id=? ORDER BY created_at DESC", (problem_id,)
            ).fetchall()
            return [self._row_to_attempt(r) for r in rows]

    def list_all(self) -> list[Attempt]:
        with get_conn() as c:
            rows = c.execute("SELECT * FROM attempts ORDER BY created_at DESC").fetchall()
            return [self._row_to_attempt(r) for r in rows]

    @staticmethod
    def _row_to_attempt(row) -> Attempt:
        return Attempt(
            id=row["id"], problem_id=row["problem_id"],
            status=AttemptStatus(row["status"]),
            created_at=row["created_at"], updated_at=row["updated_at"],
        )


class SubmissionRepository:
    def add(self, s: Submission) -> None:
        with get_conn() as c:
            c.execute(
                "INSERT INTO submissions VALUES (?,?,?,?,?)",
                (s.id, s.attempt_id, s.format.value, s.content, s.created_at),
            )

    def latest_for_attempt(self, attempt_id: str) -> Optional[Submission]:
        with get_conn() as c:
            row = c.execute(
                "SELECT * FROM submissions WHERE attempt_id=? ORDER BY created_at DESC LIMIT 1",
                (attempt_id,),
            ).fetchone()
            return self._row_to_submission(row) if row else None

    def get(self, submission_id: str) -> Optional[Submission]:
        with get_conn() as c:
            row = c.execute("SELECT * FROM submissions WHERE id=?", (submission_id,)).fetchone()
            return self._row_to_submission(row) if row else None

    @staticmethod
    def _row_to_submission(row) -> Submission:
        return Submission(
            id=row["id"], attempt_id=row["attempt_id"],
            format=SubmissionFormat(row["format"]), content=row["content"],
            created_at=row["created_at"],
        )


class EvaluationResultRepository:
    def add(self, r: EvaluationResult) -> None:
        with get_conn() as c:
            c.execute(
                "INSERT INTO evaluation_results VALUES (?,?,?,?,?,?,?,?,?)",
                (r.id, r.submission_id, r.source, r.score,
                 dumps(r.strengths), dumps(r.issues), dumps(r.suggestions),
                 r.notes, r.created_at),
            )

    def for_submission(self, submission_id: str) -> list[EvaluationResult]:
        with get_conn() as c:
            rows = c.execute(
                "SELECT * FROM evaluation_results WHERE submission_id=? ORDER BY created_at",
                (submission_id,),
            ).fetchall()
            return [self._row_to_result(r) for r in rows]

    @staticmethod
    def _row_to_result(row) -> EvaluationResult:
        return EvaluationResult(
            id=row["id"], submission_id=row["submission_id"], source=row["source"],
            score=row["score"], strengths=loads(row["strengths"], []),
            issues=loads(row["issues"], []), suggestions=loads(row["suggestions"], []),
            notes=row["notes"] or "", created_at=row["created_at"],
        )
