# AI Usage

Built with Claude as a pair-programmer. Five decisions worth calling out:

1. **Evaluator architecture — accepted, with a rejection.**
   Claude's first suggestion was a single `evaluate(problem, submission)` function with an
   `if use_llm:` branch inside it. I rejected that and asked for a proper `EvaluationStrategy`
   interface with `DeterministicEvaluator`, `LLMEvaluator`, and a `CompositeEvaluator` that
   composes them, specifically because the assignment asks "how would your design accommodate
   another evaluation approach later" — a branch inside one function doesn't answer that
   question, a strategy interface does.

2. **Graceful degradation on LLM failure — accepted and hardened.**
   Claude proposed catching LLM errors and returning an error response to the frontend. I
   changed this: `CompositeEvaluator` catches `LLMEvaluatorError` and falls back to the
   deterministic result with a `notes` field explaining what's missing, so a missing API key
   or a network blip degrades the *quality* of feedback, not the *availability* of it. This
   was tested explicitly (`TestCompositeEvaluatorDegradesGracefully`) rather than left as an
   unverified claim.

3. **Attempt status as an enum + explicit transition table — accepted.**
   Claude suggested this after I asked how to avoid "impossible states" like evaluating a
   draft attempt or double-submitting an evaluated one. I accepted the state-machine approach
   (`AttemptStatus.legal_transitions()` + `transition_to()` raising on illegal moves) because
   it turns a rule that would otherwise live only in the design note into something a test
   actually enforces.

4. **Provider SDK vs. raw `requests` call — rejected the SDK, and this paid off when I
   switched providers.**
   Claude's default was to use a vendor SDK (`google-generativeai` for Gemini). I rejected
   that: the sandbox this was built in has no network access to install packages, and a raw
   `requests.post` to a single REST endpoint is one function, one fewer dependency to install
   for anyone running this later, and makes the exact request/response shape visible in the
   code instead of hidden behind an SDK. This decision mattered in practice — the project was
   originally built against the Anthropic Messages API and I later switched to Gemini
   (`GEMINI_API_KEY`) because I didn't have a paid Anthropic key. Because `LLMEvaluator` was
   already isolated behind the `EvaluationStrategy` interface and used a plain REST call, the
   swap was a single-file change (new URL, new auth header, new response-parsing shape) with
   no changes to `CompositeEvaluator`, `EvaluationService`, or the API layer — which is exactly
   what that interface boundary was for.

5. **Deterministic evaluator: AST parsing vs. keyword/pattern heuristics — accepted the
   simpler option, with a documented trade-off.**
   I asked Claude whether to actually parse submitted code. It pointed out submissions can be
   free-text design prose, pseudocode, or code in any language — a parser would need
   per-language support and would reject valid non-code answers outright, which contradicts
   "text, code, diagram, or a combination" in the assignment. I accepted keyword/structural
   heuristics (does it mention the core entities, does it use relationship language, does it
   name class-like tokens) instead, and made sure this trade-off is stated explicitly in
   `docs/design_note.md` rather than presented as more rigorous than it is.

Everything above was reviewed and, in several cases, tested (see `tests/test_domain.py`)
before being accepted — none of it was taken as-is without checking it actually does what it
claims to.
