# Change Log

## 2026-04-22

### Bootstrap Baseline

- added the initial Sprint 2 project scaffold under `app/` and `tests/`
- created configuration, models, utilities, and first-pass service modules
- added local sample fixtures for schema-drift, route-drift, and auth-drift
- introduced repository docs for product context and mandatory change tracking
- namespaced config variables under `REMORPH_` after catching an env collision during validation
- verified the scaffold with `run_local_test.py` and a passing `pytest` run
- tightened pre-push hygiene by ignoring local-only files and documenting the run flow
- upgraded `run_local_test.py` into a small CLI for smoke tests and full healing runs
- corrected the ignore rule so both `.codex` files and `.codex/` directories stay local
- added deterministic repair logic so full healing can handle the core demo scenarios without depending on live LLM access
- added a dedicated run and validation guide covering setup, commands, and expected outputs for all demo scenarios
- hardened the LLM client so malformed model output becomes a safe fallback instead of a crash
- enabled Groq JSON mode for healing calls and removed the hardcoded API key from tracked config
- added model-aware structured output selection and reduced LiteLLM console noise during runs
- upgraded Sprint 2 with integration diagnostics and documented team ownership plus detailed folder responsibilities
- refreshed the run guide to reflect venv-based commands, diagnostics in healed output, and the direct integration entry point
- implemented the remaining Sprint 2 integration layer: proxy adapter, retry orchestrator, telemetry sink, repair cache, and stronger route matching
- added Jenish and Sachin handoff docs plus tests for cache, route matching, and retry flow
- fixed retry-orchestrator test isolation so local Groq keys do not make the suite nondeterministic
- hardened Sprint 2 further with docs metadata, schema confidence/completeness, explicit proxy failure reasons, and richer training telemetry fields
