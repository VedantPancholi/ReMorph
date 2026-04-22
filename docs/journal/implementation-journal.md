# Implementation Journal

## 2026-04-22 - Repository Bootstrap

### Goal

Set up the ReMorph repository so implementation can continue with production
discipline and explicit written context for every future change.

### What Changed

- created the Sprint 2 application scaffold
- added typed request, response, and schema models
- implemented base config, logger, JSON helpers, and error types
- implemented initial doc loading, URL parsing, prompt building, and schema
  extraction logic
- added a sample OpenAPI document and three trapped-error fixtures
- created the docs ledger for context, changes, and implementation notes

### Files Touched

- `README.md`
- `.gitignore`
- `.env.example`
- `requirements.txt`
- `app/`
- `docs/`
- `tests/`

### Assumptions

- Sprint 2 owns the reasoning/healing layer only
- OpenAPI JSON is the first-class contract source for now
- local sample fixtures should be available before proxy integration

### Risks And Follow-Ups

- `llm_client.py` is wired for real provider calls but still needs live
  environment validation
- route drift heuristics are intentionally lightweight and may need refinement
- the orchestration flow is ready for extension but not yet integration-tested

### Validation Note

During local validation, machine-level environment variables collided with the
initial generic settings names such as `DEBUG`. The config layer was updated to
use the `REMORPH_` prefix so the project can run consistently across laptops,
CI, and containers.

### Verification

- `run_local_test.py` succeeded against the local sample OpenAPI file
- `.venv/bin/pytest -q` passed with 6 tests

## 2026-04-22 - Pre-Push Cleanup

### Goal

Make the repository safe to push and easy for collaborators to run without
guessing the current status or local commands.

### What Changed

- ignored `.codex/` and `from_gpt_context.txt` as local-only artifacts
- corrected the ignore rules to also cover a `.codex` file at repo root
- expanded `README.md` with readiness status and run instructions
- upgraded `run_local_test.py` to support both smoke and full healing modes
- updated project context to reflect the current implementation status

### Files Touched

- `.gitignore`
- `README.md`
- `run_local_test.py`
- `docs/context/project-context.md`
- `docs/changes/change-log.md`
- `docs/journal/implementation-journal.md`

### Assumptions

- the raw ChatGPT export should stay local because its distilled project intent
  already exists in repository docs
- collaborators benefit from one obvious runner instead of several ad hoc commands

## 2026-04-22 - Demo-Strong Healing Layer

### Goal

Upgrade the healing engine so the repository can demonstrate real request
repair behavior even when a model key is unavailable or provider access fails.

### What Changed

- added `app/services/deterministic_repair.py` for rule-based payload, route,
  and auth repair
- updated the schema extraction path to annotate field names for deterministic
  payload remapping
- changed `healer.py` to prepare a deterministic repair first and only use the
  LLM as an optional refinement path
- expanded healer tests to cover fallback payload, route, and auth repair
- updated repository docs to explain that full healing now works locally

### Files Touched

- `app/services/deterministic_repair.py`
- `app/services/schema_extractor.py`
- `app/services/healer.py`
- `tests/test_healer.py`
- `README.md`
- `docs/context/project-context.md`
- `docs/changes/change-log.md`
- `docs/journal/implementation-journal.md`

### Outcome

The three demo scenarios now produce a structured healed request locally:

- payload drift repairs nested body shape
- route drift repairs the path and can also repair auth if the new endpoint
  demands it
- auth drift converts bearer tokens into the documented API key header

## 2026-04-22 - Operator Runbook

### Goal

Give the team a single markdown file that explains how to run the project and
how to judge whether the healed output is correct.

### What Changed

- added `docs/context/run-and-test-guide.md`
- linked the new runbook from `README.md`
- recorded the new operational documentation in the change ledger

### Files Touched

- `docs/context/run-and-test-guide.md`
- `README.md`
- `docs/changes/change-log.md`
- `docs/journal/implementation-journal.md`

## 2026-04-22 - LLM Output Hardening

### Goal

Prevent model-side formatting mistakes from crashing `--mode heal` when the
provider returns prose, fenced output, or malformed JSON.

### What Changed

- hardened `llm_client.py` to extract a JSON object from wrapped model output
- converted JSON decode and validation failures into `LLMHealingError`
- updated `healer.py` to log the failure reason and fall back safely
- strengthened prompt instructions to forbid markdown or extra commentary
- added tests for wrapped JSON output and invalid model output

### Files Touched

- `app/services/llm_client.py`
- `app/services/healer.py`
- `app/services/prompt_builder.py`
- `tests/test_llm_client.py`
- `docs/context/run-and-test-guide.md`
- `docs/changes/change-log.md`
- `docs/journal/implementation-journal.md`

## 2026-04-22 - Provider JSON Mode

### Goal

Reduce malformed Groq responses by asking for JSON mode directly and remove a
credential handling mistake from tracked source.

### What Changed

- updated `llm_client.py` to pass `response_format={"type": "json_object"}`
- removed the hardcoded Groq API key from `config.py`
- updated docs to reinforce that secrets belong only in `.env`

### Files Touched

- `app/config.py`
- `app/services/llm_client.py`
- `README.md`
- `docs/context/run-and-test-guide.md`
- `docs/changes/change-log.md`
- `docs/journal/implementation-journal.md`

### Follow-Up Hardening

- Groq models with Structured Outputs support now use `json_schema`
- other Groq models now use `json_object`
- LiteLLM debug/help noise is suppressed during normal runs

## 2026-04-22 - Sprint 2 Integration Upgrade

### Goal

Make Sprint 2 more useful for Sprint 4 by exposing the runtime metadata that
the proxy, retry loop, and reward/evaluation pipeline will need later.

### What Changed

- expanded `TrappedError` with request and retry metadata
- expanded `HealedRequest` with a diagnostics block for docs source, matched
  endpoint, strategy used, fallback state, and processing time
- updated the healer to capture documentation source and attach diagnostics to
  every healing result
- refreshed sample scenarios and tests to validate the new integration fields
- documented team ownership and added a file-by-file folder explanation in the README

### Files Touched

- `app/models/request_models.py`
- `app/models/response_models.py`
- `app/services/doc_fetcher.py`
- `app/services/healer.py`
- `app/testsupport/sample_errors.py`
- `tests/test_healer.py`
- `README.md`
- `docs/context/project-context.md`
- `docs/changes/change-log.md`
- `docs/journal/implementation-journal.md`

### Outcome

Sprint 2 is still the reasoning layer, but it now returns enough operational
metadata to connect cleanly with Sprint 4 proxy retries, reward logging, and
before/after evaluation.

## 2026-04-22 - Run Guide Refresh

### Goal

Make the run instructions match the latest Sprint 2 behavior and reduce
confusion around virtualenv usage and diagnostics in the healed output.

### What Changed

- updated the run guide to prefer `.venv/bin/python` and `.venv/bin/pytest`
- documented `app.main.process_trapped_error()` as the real integration entry
  point
- added guidance for validating the new diagnostics block in healed responses

### Files Touched

- `docs/context/run-and-test-guide.md`
- `docs/changes/change-log.md`
- `docs/journal/implementation-journal.md`

## 2026-04-22 - Remaining Sprint 2 Integration Work

### Goal

Close the practical Sprint 2 gaps so the reasoning layer is usable by Jenish's
proxy and useful to Sachin's Sprint 4 reward/evaluation pipeline.

### What Changed

- added a proxy-facing adapter and repair-and-retry orchestrator
- added a persistent telemetry sink with healing and workflow summaries
- added a repair cache for repeated drift patterns
- strengthened route matching for parameterized routes
- added handoff docs for Jenish and Sachin
- expanded tests for cache, retry orchestration, and parameterized route matching

### Files Touched

- `app/config.py`
- `app/models/response_models.py`
- `app/services/repair_cache.py`
- `app/services/telemetry.py`
- `app/services/proxy_adapter.py`
- `app/services/retry_orchestrator.py`
- `app/services/healer.py`
- `app/services/schema_extractor.py`
- `tests/test_healer.py`
- `tests/test_retry_orchestrator.py`
- `tests/test_repair_cache.py`
- `tests/test_schema_matching.py`
- `README.md`
- `docs/context/project-context.md`
- `docs/context/run-and-test-guide.md`
- `docs/context/jenish-proxy-contract.md`
- `docs/context/sachin-training-handoff.md`
- `docs/changes/change-log.md`
- `docs/journal/implementation-journal.md`

### Outcome

Sprint 2 now has:

- a stable contract Jenish can integrate against
- persistent observability Sachin can use for rewards and evaluation
- reusable repair memory for repeated drift patterns
- a retry loop abstraction that bridges directly into Sprint 4

### Follow-Up Fix

Local `.env` model keys made retry-orchestrator tests nondeterministic because
they unexpectedly exercised the live LLM path. The retry tests now explicitly
clear `REMORPH_GROQ_API_KEY` so they always validate the deterministic
integration contract.

## 2026-04-22 - Sprint 2 Hardening Upgrade

### Goal

Make Sprint 2 robust enough to freeze as a reusable repair component before
moving fully into Sprint 4 system integration.

### What Changed

- upgraded docs fetching to emit spec metadata such as source, version, hash,
  and completeness flags
- upgraded schema extraction with content types, query parameters, route-match
  scores, completeness scoring, and docs confidence
- added explicit unrepairable failure outputs for the proxy-facing contract
- extended telemetry with scenario type, docs confidence, and spec metadata
- expanded tests to cover spec metadata and explicit proxy failure handling

### Files Touched

- `app/models/schema_models.py`
- `app/models/response_models.py`
- `app/services/doc_fetcher.py`
- `app/services/schema_extractor.py`
- `app/services/healer.py`
- `app/services/retry_orchestrator.py`
- `app/services/proxy_adapter.py`
- `app/services/telemetry.py`
- `app/main.py`
- `tests/test_doc_fetcher.py`
- `tests/test_schema_extractor.py`
- `tests/test_retry_orchestrator.py`
- `README.md`
- `docs/context/project-context.md`
- `docs/context/run-and-test-guide.md`
- `docs/context/jenish-proxy-contract.md`
- `docs/context/sachin-training-handoff.md`
- `docs/changes/change-log.md`
- `docs/journal/implementation-journal.md`

### Outcome

Sprint 2 now has a clearer contract, more honest confidence signals, and
explicit failure modes, which makes it much safer to embed into the Sprint 4
proxy, reward, and evaluation loop.
