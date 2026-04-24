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

## 2026-04-22 - Sprint 2 Freeze Pass

### Goal

Finish only the minimum explainability and contract work needed to freeze
Sprint 2 before full Sprint 4 implementation.

### What Changed

- added ranked route candidates and route-match reasons
- exposed explicit route-match confidence alongside existing scores
- added tests for ambiguous match, low-confidence rejection, and ranked-match recovery
- documented `process_trapped_error()` as the frozen Sprint 2 contract
- clamped weak candidate scores to `0.0` so ranked route explanations never emit invalid negative confidence values
- relaxed the ranked-match recovery assertion so the test proves recovery without depending on one brittle winner between two valid ledger candidates
- polished the main Markdown docs so setup, run steps, handoff contracts, and Sprint 2 freeze boundaries are clearer for the team
- added a Docker image definition and container run guide so the repo can be shared without requiring local Python setup

### Files Touched

- `app/models/schema_models.py`
- `app/services/schema_extractor.py`
- `tests/test_schema_extractor.py`
- `tests/test_schema_matching.py`
- `README.md`
- `docs/context/project-context.md`
- `docs/context/run-and-test-guide.md`
- `docs/context/jenish-proxy-contract.md`
- `docs/changes/change-log.md`
- `docs/journal/implementation-journal.md`
- `docs/context/change-management.md`
- `docs/context/sachin-training-handoff.md`
- `Dockerfile`
- `.dockerignore`

## 2026-04-24 - Sprint 4 Pre-Training Scoreboard Protocol

### Goal

Freeze the first repo-native baseline-vs-adaptive scoreboard on a shared eval
manifest before any supervised warm-start or RL work begins.

### What Changed

- improved grouped split logic so shared eval grouping follows the failed
  scenario fingerprint instead of policy-specific request ids
- added a scoreboard freeze protocol that builds canonical transition rows,
  persists manifests, runs baseline and adaptive on the same eval set, and
  writes comparison artifacts
- added failure-analysis outputs to surface the strongest slices, weakest
  slices, safety behavior, and training focus candidates
- updated the Sprint 4 runbook and training plan so the docs match the new
  pre-training checkpoint workflow

### Outcome

Sprint 4 now has a reproducible path to freeze one official pre-training
checkpoint from real benchmark data, which gives the project a trustworthy
baseline before any learned policy is introduced.

## 2026-04-24 - Sprint 4 Supervised Warm-Start

### Goal

Train the first learned policy on canonical supervised rows and evaluate it on
the same frozen shared eval manifest used by baseline and adaptive.

### What Changed

- added a small prototype-based supervised warm-start trainer and offline replay evaluator
- added a training CLI that reads the frozen supervised train manifest and shared eval manifest
- fixed a leakage bug where supervised rows were previously grouped by episode id
  instead of scenario fingerprint
- froze the first learned-policy checkpoint and comparison artifacts under
  `artifacts/sprint4/training/supervised_warmstart/`
- updated the Sprint 4 docs with the current manifest ids and scoreboard results

### Outcome

The first learned policy now sits between baseline and adaptive on the frozen
eval set: it beats baseline, preserves clean abstention on unrecoverable auth,
and exposes a clear repairable-slice gap that can guide future refinement.

## 2026-04-24 - Sprint 4 Error Analysis And Targeted Refinement

### Goal

Turn the warm-start gap into something actionable without pretending the next
heuristic is already better than the current checkpoint.

### What Changed

- added warm-start vs adaptive error analysis with missed-scenario counts,
  action confusion, reward gaps, support counts, and lightweight confidence
- added a deterministic refinement pipeline that reweights examples toward the
  weak repairable slices identified by the analysis
- limited top-k voting to focus scenarios so the refinement logic does not
  blindly perturb every prediction path
- added an adoption decision artifact that compares a refinement candidate
  against the frozen warm-start checkpoint on the shared eval manifest and
  refuses promotion if safety or top-line quality regresses

### Outcome

The refinement loop is now real and runnable, but the first heuristic candidate
is not promoted. That is the correct systems result: the repo gained a
reproducible refinement protocol without silently replacing the better learned
checkpoint.
