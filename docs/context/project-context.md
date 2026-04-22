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

## Current Implementation Status

The repository already contains a working baseline for Sprint 2:

- request, response, and schema models are implemented
- schema extraction works against the local sample spec
- route drift and auth metadata extraction are covered in tests
- the full healing orchestration path is wired end to end
- deterministic repair strategies now cover the core three demo scenarios without requiring a live model key
- healing responses now include diagnostics needed by proxy integration and Sprint 4 metrics

The remaining gap is not the architecture. The remaining gap is product
hardening: stronger heuristics, real provider validation, and proxy integration.

## Architecture Boundary

The intended runtime flow is:

1. Proxy traps a failure.
2. ReMorph receives the failure payload.
3. ReMorph fetches or loads the latest docs.
4. ReMorph extracts the endpoint contract.
5. ReMorph asks the model for a strict repair.
6. Proxy retries with the healed request.
