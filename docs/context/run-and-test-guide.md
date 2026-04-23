# Run And Test Guide

This is the primary runbook for the refactored ReMorph repo.

## Install

Development setup:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements/dev.txt
cp .env.example .env
```

Training/OpenEnv extras:

```bash
.venv/bin/pip install -r requirements/training.txt
```

## Repo Map

- `app/`: Sprint 2 repair brain
- `sprint4/`: benchmark, environment adapters, rewards, evaluation, training prep
- `target_api/`: live FastAPI target, spec export, and dataset generation
- `runtime/`: disposable generated outputs
- `examples/artifacts/`: tracked sample outputs

## Fastest Verification

```bash
.venv/bin/pytest -q
.venv/bin/python run_local_test.py --mode smoke --scenario a
.venv/bin/python run_local_test.py --mode heal --scenario a
```

## Local Sprint 4 Benchmark

```bash
.venv/bin/python scripts/run_benchmark.py \
  --env-mode local \
  --episodes-per-scenario 3 \
  --output-dir runtime/sprint4_local \
  --cache-mode clear \
  --disable-telemetry
```

Generate a local training dataset:

```bash
.venv/bin/python scripts/generate_sprint4_dataset.py \
  --episodes-path runtime/sprint4_local/episodes.jsonl \
  --output-dir runtime/sprint4_local/dataset \
  --eval-ratio 0.2
```

## Live Target API Benchmark

Start the live server:

```bash
.venv/bin/python -m uvicorn target_api.server.main:app --reload
```

Run the representative live benchmark:

```bash
.venv/bin/python scripts/run_benchmark.py \
  --env-mode live \
  --live-base-url http://127.0.0.1:8000 \
  --episodes-per-scenario 1 \
  --output-dir runtime/sprint4_live \
  --cache-mode disable \
  --disable-telemetry
```

Run all raw scenarios from `target_api/training_dataset.json`:

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

Run one exact raw scenario:

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

Important:

- `scenario_type` is the broad bucket:
  - `payload_drift`
  - `route_drift`
  - `auth_drift`
- `raw_scenario_type` is the exact Target API label:
  - `schema_missing_key`
  - `route_regression`
  - `auth_missing_tenant`
  - and so on

Representative live auth prefers `auth_missing_tenant`, because ReMorph can
repair a missing required header from contract evidence. A fully missing JWT is
kept as a harder negative case.

## Target API Utilities

Export the live OpenAPI spec:

```bash
.venv/bin/python -m target_api.server.export_openapi
```

Generate the Phase 1 dataset:

```bash
.venv/bin/python target_api/dataset_generator.py -m 1
```

Outputs:

- `target_api/specs/openapi.json`
- `target_api/training_dataset.json`

## Runtime Strategy

- `runtime/` is generated-only and should not be relied on as tracked state.
- `examples/artifacts/` contains preserved benchmark samples for review and demos.

## Focused Tests

```bash
.venv/bin/pytest -q \
  tests/test_server.py \
  tests/test_healer.py \
  tests/test_sprint4_benchmark_runner.py \
  tests/test_sprint4_live_api_env.py \
  tests/test_sprint4_live_scenario_loader.py
```
