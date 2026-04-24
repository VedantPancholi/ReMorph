# Change Log

## 2026-04-24

### Sprint 4 Pre-Training Scoreboard Freeze

- aligned grouped split logic around canonical scenario fingerprints so the same
  underlying benchmark case stays shared across baseline and adaptive runs even
  when request ids differ
- added the repo-native scoreboard freeze protocol under
  `sprint4/eval/scoreboard_protocol.py`
- added `scripts/freeze_sprint4_scoreboard.py` to build canonical manifests,
  run baseline/adaptive on the same shared eval manifest, and persist official
  checkpoint artifacts
- added failure-analysis outputs so training focus can be chosen from the frozen
  scoreboard rather than guessed
- refreshed Sprint 4 docs so the runbook and training plan reflect the new
  pre-training checkpoint flow

### Sprint 4 Supervised Warm-Start

- added `sprint4/training/supervised_warmstart.py` as the first learned-policy
  training and offline replay evaluation path
- added `scripts/train_sprint4_supervised.py` to train from the frozen
  supervised train manifest and evaluate on the frozen shared eval manifest
- fixed a warm-start leakage issue by carrying scenario-fingerprint group ids
  onto supervised rows before manifest creation
- froze the first learned-policy checkpoint under
  `artifacts/sprint4/training/supervised_warmstart/`
- documented the current warm-start checkpoint and scoreboard deltas in Sprint 4 docs

### Sprint 4 Error Analysis And Targeted Refinement

- added warm-start vs adaptive error-analysis artifacts with scenario misses,
  action confusion, support counts, confidence, and reward-gap reporting
- added `sprint4/training/targeted_refinement.py` and
  `scripts/refine_sprint4_warmstart.py` to build and evaluate refinement
  candidates on the same frozen shared eval manifest
- added an explicit adoption gate so refinement candidates are only promoted if
  they improve over the frozen warm-start checkpoint without regressing safety
- kept docs honest by recording that the first heuristic refinement candidate
  is not promoted and the recommended learned policy remains `warmstart`

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
- completed the Sprint 2 freeze pass with ranked route candidates, match reasons, ambiguous handling, and explicit contract documentation
- fixed the freeze-pass scorer so weak routes clamp to zero confidence and ranked-match tests stay stable across valid candidate orderings
- polished the repo Markdown set so the README, run guide, and handoff docs match the frozen Sprint 2 contract and current execution flow
- added a portable Docker setup with a non-root runtime image, trimmed build context, and documented container run commands
