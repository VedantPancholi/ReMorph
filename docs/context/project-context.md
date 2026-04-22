# Project Context

## Product Direction

ReMorph is being built as the reasoning layer for a self-healing API agent. The
core product claim is that API failures should become discovery events instead
of terminal crashes.

## Source Context

The current direction is distilled from `from_gpt_context.txt`, which describes:

- payload drift, where request structures change
- route drift, where old endpoints move or disappear
- auth drift, where security requirements change

## Team Ownership

- `Jenish`: pipe layer and proxy integration
- `Vedant`: Sprint 2 reasoning engine and Sprint 4 integration
- `Sachin`: supporting sprint delivery across environment and training work

## Sprint Connection

- Sprint 2 is the repair brain
- Sprint 4 is the end-to-end system that plugs this repair brain into the proxy,
  OpenEnv, retry loop, reward logic, and training evaluation

## Sprint 2 Scope

Sprint 2 is the reasoning engine, not the proxy or transport layer. This repo
should focus on:

- validating trapped error input
- locating the most relevant OpenAPI contract
- extracting a compact route schema
- building a safe repair prompt
- returning a structured healed request

## Frozen Contract

Sprint 2 should now be treated as a stable repair module with:

- input contract: `TrappedError`
- output contract: `HealedRequest`
- primary callable: `process_trapped_error()`

The rest of the system should integrate around this boundary instead of
changing it casually.

## What Makes Sprint 2 Believable

The repair engine is strongest when it is transparent about why a repair was
chosen. The frozen baseline now includes:

- docs/spec metadata
- docs confidence and completeness signals
- route match confidence
- ranked candidate endpoints
- route match reasons
- explicit ambiguous and low-confidence handling

That makes the repair path explainable enough for both judges and teammates.

## Current Implementation Status

The repository already contains a working baseline for Sprint 2:

- request, response, and schema models are implemented
- schema extraction works against the local sample spec
- docs metadata now includes source, version, hash, and completeness signals
- route drift and auth metadata extraction are covered in tests
- the full healing orchestration path is wired end to end
- deterministic repair strategies now cover the core three demo scenarios without requiring a live model key
- healing responses now include diagnostics needed by proxy integration and Sprint 4 metrics
- proxy-facing adapters now exist for Jenish's integration boundary
- persistent telemetry and repair cache are now implemented for repeated drifts and later reward analysis
- proxy adapters now return explicit unrepairable failure reasons when repair cannot proceed safely
- route matching now exposes confidence, ranked candidate endpoints, and match reasons for judge explainability

The remaining gap is not the architecture. The remaining gap is product
hardening: stronger heuristics at production scale, real provider validation,
and full Sprint 4 environment/training integration.

## What Is Intentionally Deferred

The following work should happen after Sprint 2 freeze, not before it:

- full OpenEnv environment implementation
- reward function and training loop
- before/after evaluation harness
- live proxy deployment or FastAPI exposure if the team wants HTTP transport
- broader production-scale heuristics for large and messy specs

## Architecture Boundary

The intended runtime flow is:

1. Proxy traps a failure.
2. ReMorph receives the failure payload.
3. ReMorph fetches or loads the latest docs.
4. ReMorph extracts the endpoint contract.
5. ReMorph asks the model for a strict repair.
6. Proxy retries with the healed request.
