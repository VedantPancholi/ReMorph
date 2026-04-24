# Three Minute Pitch

## The Problem

AI agents depend on APIs, but APIs are not stable. They drift in small but painful ways:

- payload schemas change
- routes move
- auth requirements shift
- some failures become unrecoverable because credential material is missing

When that happens, most agents either fail hard or hallucinate a repair.

## The Idea

ReMorph is a self-healing API layer for agentic systems.

It wraps a request in a structured recovery loop:

1. send the request
2. trap the failure
3. inspect the contract and failure details
4. generate a repair if the problem is recoverable
5. retry and score the result

The entire loop is OpenEnv-compatible, so we can benchmark it, export RL-facing datasets, and plug it into lightweight training workflows.

## The System

ReMorph is built in layers:

- Sprint 2 repair brain:
  stable `TrappedError -> HealedRequest` reasoning for payload, route, and auth repair
- Sprint 4 runtime:
  benchmark runner, reward breakdown, dataset export, comparison reports, and OpenEnv-compatible environment adapters
- Product-facing wrapper:
  a `ReMorphClient` interface for self-healing API requests

## The Safety Story

This is the part that matters most.

ReMorph does not try to repair everything. If the failure is unrecoverable, such as a missing bearer token or malformed JWT, it emits `safe_abstain`.

That means:

- no fake tokens
- no invented credentials
- no pretending the request was recoverable

This is critical for enterprise use, where a hallucinated auth repair is often worse than a controlled failure.

## The Results

Our artifact package demonstrates two slices:

### Repairable Drift

- baseline success: `0.0`
- adaptive success: `1.0`

ReMorph repairs payload, route, and auth-related drift successfully.

### Unrecoverable Auth

- baseline safe abstention accuracy: `0.0`
- adaptive safe abstention accuracy: `1.0`

ReMorph refuses fake credentials and fails safely.

## Why It Wins

ReMorph is not just a benchmark toy.

It combines:

- a novel self-healing API environment
- a coherent reward and training pipeline
- explicit safety behavior
- product-style usage through a client wrapper
- reproducible artifact packaging for judging

## Closing

The core insight is simple:

The future of agent infrastructure is not just better models.
It is systems that can recover from real-world API drift safely.

That is what ReMorph is built to do.
