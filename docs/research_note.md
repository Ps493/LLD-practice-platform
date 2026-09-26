# Research Note

## The learner problem
Practicing LLD is easy to *start* and hard to *self-evaluate*. A learner can produce a
plausible-looking design for Parking Lot / Elevator / Vending Machine and still not know
whether their responsibility boundaries, abstractions, and trade-offs are actually sound —
because these problems rarely have one canonical answer, unlike a DSA problem with a single
correct output. The feedback loop most learners have today is: post on a forum / LeetCode
discuss and wait, ask a senior engineer, or compare against one "reference solution" that
implicitly teaches "copy this shape" rather than "here's why this shape works."

## Existing approaches, briefly
- **LeetCode / educative.io "LLD" tracks, Grokking the OOD Interview**: give problems and a
  single worked solution. Good for exposure, weak on personalized feedback — the learner
  reads someone else's answer instead of getting feedback on their own.
- **DesignGurus, ScholarHat and similar interview-prep content**: same pattern — curated
  problems + model answers + occasional quizzes, no attempt-specific critique.
- **General-purpose LLM chat (asking ChatGPT/Claude directly)**: this is what most learners
  already do, and it works surprisingly well for the *reasoning* half of feedback — but it's
  unstructured, has no memory of previous attempts, is inconsistent problem to problem, and
  can't reliably confirm the learner actually covered the problem's known shape (it can miss
  or hallucinate coverage details, and doesn't track improvement over time).
- **Code-review bots / static analysis (SonarQube-style)**: excellent for style, cyclomatic
  complexity, code smells — not for the semantic question "did you correctly separate the
  Elevator's state from the Controller's dispatch decision," which is a domain-modeling
  judgment, not a lint rule.

## Key gaps
1. No product treats an LLD attempt as something to **track and revisit** — practice is
   one-shot, not an improvement loop.
2. Feedback tools are either fully deterministic (miss design *judgment*) or fully an LLM
   chat (miss reliable *coverage* checking and consistency) — nothing combines both.
3. Nothing acknowledges that **more than one valid design exists**, so feedback either forces
   a single "correct" shape or is too vague to be actionable.
4. Submission format is usually locked to one thing (code-only, or diagram-only) with no path
   to add another later.

## Product direction
Build a small, focused practice loop — choose problem → design → submit → feedback → review →
try again — where feedback is a **composite** of:
- a fast, deterministic *coverage* check (does the attempt engage with the problem's known
  shape: entities, relationships, edge cases, extensibility signals), and
- an LLM-based *design judgment* check (responsibility boundaries, coupling, pattern fit,
  trade-off reasoning), graded against the same rubric,
so the learner gets consistent, explainable feedback even when the LLM call is slow,
unavailable, or wrong, and can see their attempts accumulate over time instead of practicing
into a void.
