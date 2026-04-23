# ReMorph

ReMorph is an API self-healing project built in layers:

- `app/`: Sprint 2 repair brain
- `sprint4/`: benchmark, reward, training, and evaluation pipeline
- `target_api/`: live FastAPI target server, OpenAPI export, and dataset generation

The repo now supports two main runtime modes:

- `local`: deterministic in-memory benchmark for fast validation
- `live`: real HTTP calls against the Target API FastAPI server

## Repo Structure

- `app/`
  Sprint 2 repair engine. This is the stable `TrappedError -> HealedRequest`
  layer and should be treated as the core reasoning brain.
- `sprint4/`
  Sprint 4 benchmark runtime, environment adapters, reward scoring, dataset
  formatting, and training-prep utilities.
- `target_api/`
  Sprint 1 live target environment:
  - `target_api/server/`
  - `target_api/specs/openapi.json`
  - `target_api/dataset_generator.py`
  - `target_api/training_dataset.json`
- `docs/`
  Main documentation hub.
- `examples/artifacts/`
  Example benchmark outputs that are safe to keep in git.
- `runtime/`
  Generated local outputs only. This should stay disposable.

## Install

Create the environment and install development dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements/dev.txt
cp .env.example .env
```

If you want training/OpenEnv extras:

```bash
.venv/bin/pip install -r requirements/training.txt
```

If you want model-assisted refinement, set:

```env
REMORPH_GROQ_API_KEY=your_key_here
```

## Core Contract

Sprint 2 remains the stable repair interface:

- input: `TrappedError`
- output: `HealedRequest`
- entry point: `app.main.process_trapped_error()`

## Local Mode

Run the deterministic local benchmark:

```bash
.venv/bin/python scripts/run_benchmark.py \
  --env-mode local \
  --episodes-per-scenario 3 \
  --output-dir runtime/sprint4_local \
  --cache-mode clear \
  --disable-telemetry
```

Generate training rows from local episodes:

```bash
.venv/bin/python scripts/generate_sprint4_dataset.py \
  --episodes-path runtime/sprint4_local/episodes.jsonl \
  --output-dir runtime/sprint4_local/dataset \
  --eval-ratio 0.2
```

## Live Mode

Start the Target API server:

```bash
.venv/bin/python -m uvicorn target_api.server.main:app --reload
```

In another terminal, run the representative live benchmark:

```bash
.venv/bin/python scripts/run_benchmark.py \
  --env-mode live \
  --live-base-url http://127.0.0.1:8000 \
  --episodes-per-scenario 1 \
  --output-dir runtime/sprint4_live \
  --cache-mode disable \
  --disable-telemetry
```

Run every raw live scenario from the Target API dataset:

```bash
.venv/bin/python scripts/run_benchmark.py \
  --env-mode live \
  --live-base-url http://127.0.0.1:8000 \
  --live-scenario-selection all \
  --episodes-per-scenario 1 \
  --output-dir runtime/sprint4_live_all \
  --cache-mode disable \
  --disable-telemetry
```

Run one exact raw live scenario:

```bash
.venv/bin/python scripts/run_benchmark.py \
  --env-mode live \
  --live-base-url http://127.0.0.1:8000 \
  --live-raw-scenario auth_missing_token \
  --episodes-per-scenario 1 \
  --output-dir runtime/sprint4_live_auth_missing_token \
  --cache-mode disable \
  --disable-telemetry
```

Representative live auth defaults to `auth_missing_tenant` because it is
repairable from contract evidence. `auth_missing_token` is still useful as a
hard negative benchmark, but ReMorph should not invent a bearer token.

## Target API

Export the live OpenAPI contract:

```bash
.venv/bin/python -m target_api.server.export_openapi
```

Generate the Phase 1 dataset:

```bash
.venv/bin/python target_api/dataset_generator.py -m 1
```

That writes:

- `target_api/specs/openapi.json`
- `target_api/training_dataset.json`

## Reports

Tracked example outputs live under:

- `examples/artifacts/sprint4_local/`
- `examples/artifacts/sprint4_live/`

Disposable run outputs live under:

- `runtime/`

Live benchmark reports keep both:

- broad `scenario_type`
- exact `raw_scenario_type`

That means many schema variations still roll up to `payload_drift` in the top
summary, while the raw labels remain visible in `benchmark_report.json` and
`episodes.jsonl`.

## Tests

Run the main suite:

```bash
.venv/bin/python -m pytest -q
```

Key focused areas:

- `tests/test_server.py`
- `tests/test_healer.py`
- `tests/test_sprint4_*`

## Docs

Start here:

- [Run And Test Guide](docs/context/run-and-test-guide.md)
- [Sprint 4 Architecture](docs/sprint4/sprint4-architecture.md)
- [Change Management](docs/context/change-management.md)
