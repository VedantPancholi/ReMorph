# Project Context

## Product Direction

ReMorph is the reasoning and recovery layer for a self-healing API agent. The
core product claim is that API failures should become discovery events instead
of terminal crashes, and that recovery should remain safe when repair is not
possible from available evidence.

## Source Context

The working direction is distilled from `from_gpt_context.txt` and the current
Sprint 4 benchmark artifacts. The system is designed around three failure
families:

- payload drift, where request structure changes
- route drift, where endpoints or methods move
- auth drift, where security requirements change

## Team Ownership

- `Jenish`: pipe layer and proxy integration
- `Vedant`: Sprint 2 reasoning engine and Sprint 4 integration
- `Sachin`: support across environment, evaluation, and training-facing work

## Sprint Connection

- Sprint 2 is the repair brain.
- Sprint 4 is the end-to-end system that wraps Sprint 2 with environment
  adapters, retry execution, reward logic, dataset export, and evaluation.

## Sprint 2 Scope

Sprint 2 remains the reasoning engine, not the transport layer. Its stable job
is to:

- validate trapped error input
- locate the most relevant OpenAPI contract
- extract a compact route schema
- build a safe repair prompt or deterministic repair path
- return a structured healed request

## Frozen Contract

Sprint 2 should be treated as a stable repair module with:

- input contract: `TrappedError`
- output contract: `HealedRequest`
- primary callable: `process_trapped_error()`

Sprint 4 is built around this boundary rather than rewriting it.

## What Makes The System Believable

The recovery path is strongest when it is transparent about why a repair was
chosen or why recovery was refused. The current baseline includes:

- docs and spec metadata
- confidence and completeness signals
- route match confidence and ranked endpoint candidates
- explicit repair diagnostics
- explicit unrepairable and safe-abstain outcomes when credentials are missing
  or invalid

That makes the workflow explainable to judges, teammates, and future training
pipelines.

## Current Implementation Status

The repository now contains an end-to-end Sprint 2 plus Sprint 4 baseline:

- Sprint 2 request, response, and schema models are implemented
- schema extraction works against local sample specs
- docs metadata includes source, version, hash, and completeness signals
- deterministic repair strategies cover payload, route, and repairable auth
  drift without requiring a live model key
- healing responses include diagnostics needed by proxy integration and Sprint 4
  evaluation
- proxy-facing adapters exist for the Sprint 2 integration boundary
- persistent telemetry and repair cache support repeated drifts and later reward
  analysis
- route matching exposes confidence, ranked candidate endpoints, and match
  reasons
- Sprint 4 benchmark runner compares baseline and adaptive behavior
- environment backends support simulated, live, and OpenEnv-compatible flows
- reward scoring now logs detailed components, not just one scalar
- unrecoverable auth cases trigger explicit `safe_abstain` outcomes rather than
  fake credential synthesis
- RL-facing policy adaptation and episode dataset export are implemented
- trained-vs-untrained comparison reporting is implemented
- a clean final evidence package exists under `runtime/sprint4_final_clean/`
- an optional TRL-style training scaffold and reward-curve export path now exist
  for later learned-policy work

## What Has Been Validated

The current repo state has already validated the following at test or artifact
level:

- repairable drift: adaptive repair succeeds where baseline fails
- unrecoverable auth: adaptive safely abstains instead of hallucinating tokens
- reward breakdown fields are written to episodes
- training-facing dataset generation works from benchmark episodes
- comparison reports are generated for baseline, adaptive, and trained-policy
  placeholders
- clean package artifacts exist for both repairable and unrecoverable slices

## Known Constraints

- Live localhost benchmarking depends on socket binding being available in the
  environment.
- Optional TRL/reward-curve generation depends on the training extras from
  `requirements/training.txt`.
- In this workspace, `.venv/bin/pytest` may have a stale shebang, so
  `.venv/bin/python -m pytest` is the reliable test entrypoint.
- If reward-curve export raises `ModuleNotFoundError: matplotlib`, install the
  training extras before rerunning the TRL command.

## What Is Still Optional

The main architecture is in place. The remaining work is refinement, not
missing infrastructure:

- stronger learned-policy training beyond the current scaffold
- real live-mode artifact generation when local socket binding is available
- larger-scale benchmark coverage and packaging polish
- productization around the `ReMorphClient` wrapper and external integrations

## Architecture Boundary

The intended runtime flow is now:

1. Proxy or benchmark runner traps a failure.
2. ReMorph packages the failure as a `TrappedError`.
3. Sprint 2 produces a deterministic or model-assisted repair candidate.
4. Sprint 4 retries the healed request or safely abstains if recovery is unsafe.
5. Reward logic records detailed success, retry, abstention, and penalty
   components.
6. Episode logs are exported into RL-facing transitions and comparison reports.
