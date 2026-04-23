# Run And Test Guide

This is the main runbook for the integrated ReMorph repo.

- Sprint 2 remains the repair brain.
- Sprint 4 now supports two environment modes:
  - `local`: deterministic in-memory benchmark env
  - `live`: Sprint 1 FastAPI target server
- Sprint 1 dataset output is available as an offline adapter input through
  `training_dataset.json`.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Optional model-assisted refinement:

```env
REMORPH_GROQ_API_KEY=your_key_here
```

If the copied virtualenv entrypoints point at an old machine path, use:

```bash
PYTHONPATH=.venv/lib/python3.12/site-packages /usr/bin/python3 ...
```

## Core Validation

Run the main local suite:

```bash
.venv/bin/pytest -q
```

Focused Sprint 4 integration coverage:

```bash
.venv/bin/pytest -q \
  tests/test_sprint4_env_factory.py \
  tests/test_sprint4_live_api_env.py \
  tests/test_sprint4_trap_and_repair.py \
  tests/test_sprint4_phase1_dataset_adapter.py \
  tests/test_sprint4_benchmark_runner.py \
  tests/test_sprint4_workflow_runner.py
```

## Sprint 4 Local Mode

Use local mode when you want fast deterministic benchmark runs.

```bash
.venv/bin/python scripts/run_benchmark.py \
  --env-mode local \
  --episodes-per-scenario 3 \
  --output-dir runtime/sprint4_local \
  --cache-mode clear \
  --disable-telemetry
```

This mode uses:

- `sprint4/env/mutable_api_env.py`
- drift contracts under `sprint4/env/contracts/`
- the same Sprint 2 repair loop as live mode

## Sprint 4 Live Mode

Use live mode when you want Sprint 4 to call the Sprint 1 FastAPI server over
HTTP.

1. Start the live server:

```bash
.venv/bin/python -m uvicorn server.main:app --reload
```

2. Run the live benchmark:

```bash
.venv/bin/python scripts/run_benchmark.py \
  --env-mode live \
  --live-base-url http://127.0.0.1:8000 \
  --episodes-per-scenario 1 \
  --output-dir runtime/sprint4_live \
  --cache-mode disable \
  --disable-telemetry
```

3. Run all live raw scenarios from `training_dataset.json`:

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

4. Run one exact raw live scenario:

```bash
.venv/bin/python scripts/run_benchmark.py \
  --env-mode live \
  --live-base-url http://127.0.0.1:8000 \
  --live-raw-scenario schema_missing_key \
  --episodes-per-scenario 1 \
  --output-dir runtime/sprint4_live_schema_missing_key \
  --cache-mode disable \
  --disable-telemetry
```

Live mode uses:

- `sprint4/env/live_api_env.py`
- `specs/openapi.json` as the repair spec
- live HTTP status codes including `422`
- richer response parsing from `actual_server_response`

Default representative live scenarios are chosen to be meaningful for repair:

- `payload_drift` -> prefers `schema_missing_key`
- `route_drift` -> prefers `route_regression`
- `auth_drift` -> prefers `auth_missing_tenant`

The representative auth case is `auth_missing_tenant` because it is repairable
from contract evidence. A totally missing JWT such as `auth_missing_token`
remains a valid benchmark case, but ReMorph cannot safely invent a bearer token
from nothing.

Important labeling note:

- `scenario_type` is the broad Sprint 4 bucket:
  - `payload_drift`
  - `route_drift`
  - `auth_drift`
- `raw_scenario_type` is the exact Sprint 1 label:
  - `schema_missing_key`
  - `schema_type_coercion`
  - `route_regression`
  - `auth_missing_token`
  - and so on

So if you run multiple schema mutations, they will all still appear under
`payload_drift` in the top-level summary. Use `raw_scenario_type` or the
`Per Raw Scenario Accuracy` section to distinguish them.

To benchmark an unrecoverable auth case directly:

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

## Sprint 1 Dataset Adapter

Generate the Phase 1 live dataset:

```bash
.venv/bin/python dataset_generator.py -m 1
```

That writes `training_dataset.json`.

Sprint 4 can consume it for offline analysis and replay seeding through:

- `sprint4/training/phase1_dataset_adapter.py`

The adapter preserves:

- raw live scenario names such as `schema_missing_key`
- mapped Sprint 4 categories such as `payload_drift`
- parsed validation/auth/route signals from stringified server responses

## Dataset And Training Prep

Generate training rows from benchmark episodes:

```bash
.venv/bin/python scripts/generate_sprint4_dataset.py \
  --episodes-path runtime/sprint4_local/episodes.jsonl \
  --output-dir runtime/sprint4_local/dataset \
  --eval-ratio 0.2
```

Prepare TRL-ready train/eval artifacts:

```bash
.venv/bin/python -m sprint4.training.trl_train_grpo \
  --episodes-path runtime/sprint4_local/episodes.jsonl \
  --output-dir runtime/sprint4_local/training \
  --eval-ratio 0.2
```

## Output Files

Main Sprint 4 outputs stay stable across local and live modes:

- `runtime/.../episodes.jsonl`
- `runtime/.../benchmark_report.json`
- `runtime/.../benchmark_summary.md`

Live benchmark reports now include both:

- `per_scenario_accuracy`
- `per_raw_scenario_accuracy`

Training-facing outputs:

- `runtime/.../dataset/train.jsonl`
- `runtime/.../dataset/eval.jsonl`
- `runtime/.../training/trl_training_summary.json`

## Notes

- Local mode should remain the default for CI and fast iteration.
- Live mode is optional and should not be required for the base test suite.
- Sprint 2 entry point remains `app.main.process_trapped_error()`.
