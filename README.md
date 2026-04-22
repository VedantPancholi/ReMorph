# ReMorph

ReMorph is the Sprint 2 reasoning layer for a self-healing API agent. The
system takes a trapped API failure, inspects the latest contract, and prepares a
safe repair for payload drift, route drift, or auth drift.

## Current Focus

The repository is being bootstrapped around the context captured in
`from_gpt_context.txt`. The first milestone is a production-style scaffold with:

- typed models for trapped failures and healed responses
- configuration and logging primitives
- OpenAPI fetching and schema extraction foundations
- a lightweight documentation system that records every code change

## Configuration

Environment variables are namespaced with the `REMORPH_` prefix to avoid
collisions with machine-level settings. Start from `.env.example` when wiring a
local `.env`.

## What Is Ready Now

- typed input and output models for trapped errors and healed requests
- config, logging, JSON helpers, and custom error types
- local OpenAPI loading plus remote docs probe scaffolding
- schema extraction for nested request bodies, `$ref` resolution, and security schemes
- route matching that can recover the closest route when the original path drifts
- prompt construction for the healing model
- deterministic repair strategies for payload, route, and auth drift
- a local CLI harness for smoke tests and full healing attempts
- a passing test suite for the current baseline

## What Is Not Ready Yet

- proxy integration or HTTP server exposure
- persistent caching or memory of previous repairs
- stronger route matching heuristics for large specs
- live end-to-end validation against a real provider key

## How To Run

1. Create and activate a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`.
4. Add `REMORPH_GROQ_API_KEY` if you want model-assisted healing refinement.

### Smoke Test

This validates the local sample OpenAPI file and route/schema extraction without
calling the LLM:

```bash
.venv/bin/python run_local_test.py --mode smoke --scenario a
```

Scenario choices:

- `a`: payload drift
- `b`: route drift
- `c`: auth drift

### Full Healing Run

This runs the full orchestration path. It now works without a provider key by
using deterministic repairs first, and it can optionally refine through the
configured model when `REMORPH_GROQ_API_KEY` is present:

```bash
.venv/bin/python run_local_test.py --mode heal --scenario a
```

### Automated Tests

```bash
.venv/bin/pytest -q
```

## Current Runtime Flow

1. `process_trapped_error()` validates the trapped failure payload.
2. `heal_request()` loads the spec and extracts the best-matching route schema.
3. `prompt_builder` creates the repair prompt from the failure and normalized schema.
4. `llm_client` calls the configured model and validates the strict JSON response.
5. The caller receives a structured healed request object.

## Demo Strength

The fallback repair path is now strong enough to demonstrate the three core
scenarios locally:

- Scenario A: payload rewritten into the nested schema
- Scenario B: route updated and auth header migrated to `x-api-key`
- Scenario C: bearer auth converted into the required API key header

## Repository Layout

- `app/`: application code
- `tests/`: automated tests
- `docs/context/`: product context, architecture, and working agreements
- `docs/changes/`: concise running change log
- `docs/journal/`: implementation notes with what changed and why

## Change Tracking Rule

Every future code change should be accompanied by a doc update. The working
agreement for that process lives in [docs/context/change-management.md](/home/matter/Documents/ReMorph/docs/context/change-management.md).
