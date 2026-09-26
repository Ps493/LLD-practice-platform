"""
Evaluation strategies.

Design question this file answers: "which parts of evaluation should be
deterministic, and which benefit from an LLM?"

- DeterministicEvaluator: fast, free, 100% reproducible. It checks *coverage*
  signals a program can actually verify without understanding design quality —
  did the learner mention the core entities the problem expects, did they
  express relationships/behaviour (not just a flat list of fields), did they
  address at least one extensibility/edge-case concern. It cannot judge
  whether an abstraction is *good*, only whether the attempt engages with the
  problem's known shape. This always runs and always succeeds.

- LLMEvaluator: judges the things a static check can't — responsibility
  boundaries, coupling, whether the chosen pattern fits, trade-off reasoning.
  This is the part that can be slow or fail (network/timeout/rate limit), so
  it is isolated behind its own try/except and never blocks the deterministic
  result from being shown.

- CompositeEvaluator: runs both, merges them, and degrades gracefully if the
  LLM call fails — the learner still gets the deterministic feedback instead
  of a spinner or an error page. This is the extensibility seam: a future
  evaluator (e.g. a static-analysis-of-actual-code evaluator, or a second LLM
  as a critic/debate pair) is just another EvaluationStrategy added to the
  `strategies` list, with no change to the service or API layer.
"""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod

import requests

from models import EvaluationResult, Problem, Submission, new_id


class EvaluationStrategy(ABC):
    source_name: str = "base"

    @abstractmethod
    def evaluate(self, problem: Problem, submission: Submission) -> EvaluationResult:
        ...


class DeterministicEvaluator(EvaluationStrategy):
    source_name = "deterministic"

    RELATIONSHIP_HINTS = ["extends", "implements", "has-a", "has a", "uses", "contains",
                           "->", "interface", "abstract", "inherits"]
    EDGE_CASE_HINTS = ["edge case", "concurrency", "thread", "fail", "error", "invalid",
                        "what if", "race condition", "null", "empty"]
    EXTENSIBILITY_HINTS = ["extend", "extensib", "plug", "strategy", "new type",
                            "add support", "future", "swap", "interface"]

    def evaluate(self, problem: Problem, submission: Submission) -> EvaluationResult:
        text = submission.content.lower()

        found_entities = [e for e in problem.core_entities if e.lower() in text]
        missing_entities = [e for e in problem.core_entities if e.lower() not in text]

        has_relationships = self._any_hint(text, self.RELATIONSHIP_HINTS)
        has_edge_cases = self._any_hint(text, self.EDGE_CASE_HINTS)
        has_extensibility = self._any_hint(text, self.EXTENSIBILITY_HINTS)
        class_count = self._count_class_like_tokens(submission.content)

        coverage_ratio = len(found_entities) / max(1, len(problem.core_entities))
        score = round(
            coverage_ratio * 50
            + (15 if has_relationships else 0)
            + (15 if has_edge_cases else 0)
            + (10 if has_extensibility else 0)
            + min(10, class_count * 2)
        )
        score = max(0, min(100, score))

        strengths, issues, suggestions = [], [], []

        if found_entities:
            strengths.append(f"Covers {len(found_entities)}/{len(problem.core_entities)} expected core entities: "
                              f"{', '.join(found_entities)}.")
        if has_relationships:
            strengths.append("Expresses relationships between classes (not just a flat field list).")
        if has_extensibility:
            strengths.append("Shows awareness of extensibility (interfaces/strategy-like language).")

        if missing_entities:
            issues.append(f"No mention of: {', '.join(missing_entities)}. These are expected in most solid solutions.")
        if not has_relationships:
            issues.append("Couldn't detect explicit relationships (inheritance, composition, interfaces) between entities.")
        if not has_edge_cases:
            issues.append("No edge cases or failure scenarios discussed.")
        if class_count == 0:
            issues.append("No clear class/interface names detected — consider naming your abstractions explicitly.")

        if missing_entities:
            suggestions.append(f"Think through the responsibility of {missing_entities[0]} — what does it own, "
                                f"and who talks to it?")
        if not has_edge_cases:
            suggestions.append("Add at least one edge case (concurrent access, invalid input, capacity exceeded) "
                                "and describe how your design handles it.")
        if not has_extensibility:
            suggestions.append("State one way a new requirement (e.g. a new payment type, a new vehicle type) "
                                "would slot into your design without modifying existing classes.")

        return EvaluationResult(
            id=new_id(), submission_id=submission.id, source=self.source_name,
            score=score, strengths=strengths, issues=issues, suggestions=suggestions,
            notes="Rule-based coverage check — verifies your solution engages with the problem's known "
                  "shape. It cannot judge whether your abstractions are actually well designed.",
        )

    @staticmethod
    def _any_hint(text: str, hints: list[str]) -> bool:
        return any(h in text for h in hints)

    @staticmethod
    def _count_class_like_tokens(content: str) -> int:
        # crude but format-agnostic: "class Foo", "interface Foo", "Foo {" or "Foo:" at line start
        patterns = [
            r"\bclass\s+\w+", r"\binterface\s+\w+", r"\babstract\s+class\s+\w+",
            r"^\s*[A-Z]\w+\s*\{", r"^\s*[A-Z]\w+\s*:\s*$",
        ]
        count = 0
        for p in patterns:
            count += len(re.findall(p, content, re.MULTILINE))
        return count


class LLMEvaluatorError(Exception):
    pass


class LLMEvaluator(EvaluationStrategy):
    """Calls the Gemini API (generateContent) for reasoning-based feedback.

    Isolated and best-effort by design: any failure (missing API key, network
    error, bad JSON from the model, timeout) raises LLMEvaluatorError, which
    the CompositeEvaluator catches so the learner is never blocked on this.
    Provider is swappable: this class is the only place that knows it's
    talking to Gemini specifically — see docs/design_note.md.
    """
    source_name = "llm"
    MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
    API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    TIMEOUT_SECONDS = 20

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

    def evaluate(self, problem: Problem, submission: Submission) -> EvaluationResult:
        if not self.api_key:
            raise LLMEvaluatorError("GEMINI_API_KEY not configured")

        prompt = self._build_prompt(problem, submission)
        try:
            resp = requests.post(
                self.API_URL_TEMPLATE.format(model=self.MODEL),
                headers={
                    "x-goog-api-key": self.api_key,
                    "content-type": "application/json",
                },
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 900, "temperature": 0.2},
                },
                timeout=self.TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError(f"no candidates in response: {data}")
            parts = candidates[0].get("content", {}).get("parts", [])
            raw_text = "".join(p.get("text", "") for p in parts)
            parsed = self._parse_json(raw_text)
        except requests.RequestException as e:
            raise LLMEvaluatorError(f"Request to Gemini API failed: {e}") from e
        except (ValueError, KeyError) as e:
            raise LLMEvaluatorError(f"Could not parse model response: {e}") from e

        return EvaluationResult(
            id=new_id(), submission_id=submission.id, source=self.source_name,
            score=parsed.get("score"),
            strengths=parsed.get("strengths", []),
            issues=parsed.get("issues", []),
            suggestions=parsed.get("suggestions", []),
            notes="Reasoning-based review from an LLM grounded in this problem's rubric.",
        )

    @staticmethod
    def _build_prompt(problem: Problem, submission: Submission) -> str:
        return f"""You are reviewing a Low-Level Design (LLD) practice submission.

Problem: {problem.title} ({problem.difficulty})
Summary: {problem.summary}
Requirements:
{chr(10).join('- ' + r for r in problem.requirements)}

Rubric (what a strong answer covers):
{chr(10).join('- ' + r for r in problem.rubric)}

Learner's submission ({submission.format.value}):
---
{submission.content}
---

Judge responsibility boundaries, cohesion/coupling, whether patterns used fit
the problem, and trade-off reasoning. There can be more than one valid design
— do not penalize a reasonable alternative to the "expected" entities.
Respond with ONLY a JSON object, no prose, no markdown fences, in this exact shape:
{{"score": <0-100 int>, "strengths": [<=4 short strings], "issues": [<=4 short strings], "suggestions": [<=4 short, actionable strings]}}"""

    @staticmethod
    def _parse_json(raw_text: str) -> dict:
        cleaned = raw_text.strip()
        cleaned = re.sub(r"^```(json)?|```$", "", cleaned, flags=re.MULTILINE).strip()
        return json.loads(cleaned)


class CompositeEvaluator(EvaluationStrategy):
    """Runs deterministic (always) + LLM (best-effort) and merges them.

    This is the answer to "what should happen if evaluation takes time or
    fails": the deterministic pass is synchronous and instant, so the learner
    always gets *something*. The LLM pass is attempted inline with a short
    timeout for this prototype; if it fails or times out we still return the
    deterministic result with a note explaining what's missing, rather than
    surfacing an error. See docs/design_note.md for how this would move to a
    background job + polling if AI evaluation needed to be slower/queued.
    """
    source_name = "composite"

    def __init__(self, llm_evaluator: LLMEvaluator | None = None):
        self.deterministic = DeterministicEvaluator()
        self.llm = llm_evaluator or LLMEvaluator()

    def evaluate(self, problem: Problem, submission: Submission) -> EvaluationResult:
        det = self.deterministic.evaluate(problem, submission)
        try:
            llm = self.llm.evaluate(problem, submission)
        except LLMEvaluatorError as e:
            return EvaluationResult(
                id=new_id(), submission_id=submission.id, source=self.source_name,
                score=det.score, strengths=det.strengths, issues=det.issues,
                suggestions=det.suggestions,
                notes=f"LLM evaluation unavailable ({e}); showing deterministic coverage check only.",
            )

        merged_score = round((det.score + (llm.score or det.score)) / 2) if llm.score is not None else det.score
        return EvaluationResult(
            id=new_id(), submission_id=submission.id, source=self.source_name,
            score=merged_score,
            strengths=self._dedupe(det.strengths + llm.strengths),
            issues=self._dedupe(det.issues + llm.issues),
            suggestions=self._dedupe(det.suggestions + llm.suggestions),
            notes="Deterministic coverage check + LLM design review, combined.",
        )

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        seen, out = set(), []
        for i in items:
            if i not in seen:
                seen.add(i)
                out.append(i)
        return out[:6]
