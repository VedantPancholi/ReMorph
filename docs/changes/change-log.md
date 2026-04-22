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
