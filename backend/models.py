"""
Domain models for the LLD Practice Platform.

This module is the "core design" the assignment asks for: the important
domain behaviour expressed as classes with clear responsibilities, rather
than as loose dicts passed around the codebase.

Design notes (see docs/design_note.md for the full write-up):
- Problem, Attempt, Submission and EvaluationResult are plain, persistence-
  agnostic value/entity objects. They know nothing about SQLite or Flask.
- AttemptStatus is an explicit state machine, not a free-text string, so
  illegal transitions (e.g. evaluating a DRAFT attempt) are caught in code.
- SubmissionFormat is an enum today (TEXT_DESIGN, CODE) so a future DIAGRAM
  format is a one-line addition, not a refactor.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AttemptStatus(str, Enum):
    """Explicit state machine for an attempt's lifecycle.

    DRAFT -> SUBMITTED -> EVALUATING -> EVALUATED
                                     \\-> EVALUATION_FAILED -> EVALUATING (retry)
    """
    DRAFT = "draft"
    SUBMITTED = "submitted"
    EVALUATING = "evaluating"
    EVALUATED = "evaluated"
    EVALUATION_FAILED = "evaluation_failed"

    @staticmethod
    def legal_transitions() -> dict:
        return {
            AttemptStatus.DRAFT: {AttemptStatus.SUBMITTED},
            AttemptStatus.SUBMITTED: {AttemptStatus.EVALUATING},
            AttemptStatus.EVALUATING: {AttemptStatus.EVALUATED, AttemptStatus.EVALUATION_FAILED},
            AttemptStatus.EVALUATION_FAILED: {AttemptStatus.EVALUATING},
            AttemptStatus.EVALUATED: set(),  # terminal; a new attempt is made to retry, not reopen
        }


class IllegalStatusTransition(Exception):
    pass


class SubmissionFormat(str, Enum):
    TEXT_DESIGN = "text_design"   # free-form: responsibilities, classes, relationships in prose/pseudo-UML
    CODE = "code"                 # class/interface skeletons or full code in any language
    # Extensibility hook: DIAGRAM = "diagram" could be added later (e.g. a serialized
    # excalidraw/mermaid graph) without touching Attempt, Submission or the evaluator
    # interface — see EvaluationStrategy and docs/design_note.md "Extensibility".


@dataclass
class Problem:
    id: str
    title: str
    difficulty: str                 # "Easy" | "Medium" | "Hard"
    summary: str
    requirements: list[str]         # functional requirements the learner must satisfy
    core_entities: list[str]        # expected domain nouns, used by the deterministic evaluator
    rubric: list[str]                # human-readable evaluation criteria, also fed to the LLM evaluator
    tags: list[str] = field(default_factory=list)


@dataclass
class Submission:
    id: str
    attempt_id: str
    format: SubmissionFormat
    content: str
    created_at: str = field(default_factory=now_iso)


@dataclass
class EvaluationResult:
    id: str
    submission_id: str
    source: str                      # "deterministic" | "llm" | "composite"
    score: Optional[int]             # 0-100, None if this component could not run
    strengths: list[str]
    issues: list[str]
    suggestions: list[str]
    notes: str = ""                  # e.g. "LLM evaluation unavailable, showing deterministic-only feedback"
    created_at: str = field(default_factory=now_iso)


@dataclass
class Attempt:
    id: str
    problem_id: str
    status: AttemptStatus = AttemptStatus.DRAFT
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def transition_to(self, new_status: AttemptStatus) -> None:
        allowed = AttemptStatus.legal_transitions().get(self.status, set())
        if new_status not in allowed:
            raise IllegalStatusTransition(
                f"Cannot move attempt {self.id} from {self.status} to {new_status}"
            )
        self.status = new_status
        self.updated_at = now_iso()
