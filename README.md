# ReMorph

ReMorph is the Sprint 2 repair engine for a self-healing API agent. It takes a
trapped API failure, inspects the latest contract, and returns a structured
repair for payload drift, route drift, or auth drift.

## Why This Repo Exists

The project is built from the product direction captured in
`from_gpt_context.txt`. The goal of Sprint 2 is not to build the whole system.
The goal is to freeze one believable, explainable, integration-ready repair
module that Sprint 4 can plug into a proxy, environment, retry loop, and reward
pipeline.

## Quick Start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/pytest -q
.venv/bin/python run_local_test.py --mode heal --scenario a
```

If you want model-assisted refinement, add `REMORPH_GROQ_API_KEY` to `.env`.
The local demo still works without it because deterministic repair is already
implemented.

## Docker Quick Start

If you want to share the repo without requiring local Python setup:

```bash
docker build -t remorph .
docker run --rm remorph
docker run --rm remorph --mode heal --scenario a
```

If you want model-assisted refinement inside Docker, pass the local `.env` file:

```bash
docker run --rm --env-file .env remorph --mode heal --scenario a
```

If you want runtime cache and telemetry artifacts to persist on the host:

```bash
docker run --rm --env-file .env -v "$(pwd)/runtime:/app/runtime" remorph --mode heal --scenario a
```

## Configuration

All environment variables use the `REMORPH_` prefix to avoid collisions with
machine-level settings.

Important:

- keep `REMORPH_GROQ_API_KEY` only in `.env`
- do not hardcode provider keys in tracked Python files
- prefer `.venv/bin/python` and `.venv/bin/pytest` unless the venv is already active

## What Sprint 2 Already Delivers

- typed request, response, diagnostics, schema, and proxy-contract models
- local OpenAPI loading plus multi-source docs-fetch scaffolding
- docs metadata including source, version, hash, fetch state, and completeness flags
- schema extraction for nested bodies, query parameters, multiple content types, `$ref` resolution, and security schemes
- route matching with confidence, ranked candidates, and match reasons
- deterministic repair strategies for payload, route, auth, and combined drift
- optional model refinement with safe fallback on invalid model output
- proxy-facing adapter and retry orchestration
- persistent telemetry and reusable repair cache
- explicit unrepairable failure responses
- a local CLI harness and passing automated test suite

## What Sprint 2 Does Not Try To Be

- not the HTTP proxy itself
- not the OpenEnv environment
- not the reward function or training pipeline
- not the final Sprint 4 evaluation harness

Those pieces belong to the next phase once the repair engine contract is frozen.

## Frozen Sprint 2 Contract

Sprint 2 should now be treated as a stable repair component:

- input: `TrappedError`
- output: `HealedRequest`
- primary callable: `app.main.process_trapped_error()`

For safer orchestration and explicit failure reasons, integrations can also use:

- `app.main.process_trapped_error_safe()`
- `app.services.proxy_adapter.handle_proxy_failure()`
- `app.services.proxy_adapter.handle_proxy_failure_with_retry()`

## Runtime Flow

1. A proxy traps an upstream API failure.
2. ReMorph loads the latest docs or spec bundle.
3. ReMorph extracts the best endpoint contract with explainable route matching.
4. ReMorph builds a repair context and prepares a deterministic baseline.
5. The model may refine the repair if configured.
6. ReMorph returns a structured healed request with diagnostics.

## Demo Strength

The current local baseline is strong enough to show the three core cases:

- Scenario A: payload rewritten into the nested `user` schema
- Scenario B: route migrated to `/api/v2/finance/ledger` and auth rewritten
- Scenario C: bearer auth converted into `x-api-key`

## Optional Upgrades After Freeze

These are upgrades worth doing later, but they are no longer required to freeze
Sprint 2:

- stronger route heuristics for large, noisy specs
- broader auth support such as OAuth2, cookie auth, and basic auth
- FastAPI exposure if the team wants HTTP instead of direct Python integration
- live end-to-end validation with the chosen provider and production-like docs sources

## Repository Layout

- `app/`: main application package
- `app/config.py`: environment-driven configuration
- `app/constants.py`: shared enums and repair constants
- `app/main.py`: stable integration entry points
- `app/models/`: typed contracts for requests, repairs, schemas, and workflows
- `app/services/doc_fetcher.py`: spec loading, docs probing, and spec metadata
- `app/services/schema_extractor.py`: route matching, completeness scoring, and normalized endpoint extraction
- `app/services/deterministic_repair.py`: deterministic repair engine
- `app/services/healer.py`: end-to-end healing orchestration
- `app/services/llm_client.py`: model call and structured-output parsing
- `app/services/prompt_builder.py`: strict prompt generation
- `app/services/proxy_adapter.py`: Jenish-facing repair contract
- `app/services/retry_orchestrator.py`: repair-and-retry workflow logic
- `app/services/telemetry.py`: persistent healing and workflow telemetry
- `app/services/repair_cache.py`: reusable repair memory keyed by drift signature
- `app/testsupport/`: sample OpenAPI spec and trapped-error fixtures
- `app/utils/`: logging, JSON utilities, and error helpers
- `tests/`: automated coverage for schema extraction, repair logic, proxy flow, cache, and telemetry
- `Dockerfile`: portable container image for local runs and demos
- `.dockerignore`: trims the Docker build context and keeps secrets/local artifacts out of the image
- `docs/context/`: runbooks, contracts, project notes, and team handoff docs
- `docs/changes/`: change log for repo-level traceability
- `docs/journal/`: implementation journal with why each change happened
- `runtime/`: local cache and telemetry artifacts generated during runs

## Team Ownership

- `Jenish`: Sprint 1 proxy and transport/integration layer
- `Vedant`: Sprint 2 repair engine and Sprint 4 system integration
- `Sachin`: Sprint 3 support across environment, training, and evaluation delivery

## Change Tracking Rule

Every code edit should ship with a documentation update. The working agreement
for that process lives in [docs/context/change-management.md](/home/matter/Documents/ReMorph/docs/context/change-management.md).

## Runbook And Handoffs

- run and validation guide: [docs/context/run-and-test-guide.md](/home/matter/Documents/ReMorph/docs/context/run-and-test-guide.md)
- proxy contract for Jenish: [docs/context/jenish-proxy-contract.md](/home/matter/Documents/ReMorph/docs/context/jenish-proxy-contract.md)
- training and reward handoff for Sachin: [docs/context/sachin-training-handoff.md](/home/matter/Documents/ReMorph/docs/context/sachin-training-handoff.md)
