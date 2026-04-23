# ReMorph

ReMorph is the self-healing API agent project built across multiple sprint
phases.

- Sprint 1 provides the live mock server, OpenAPI contract export, and chaos
  gym / fuzzing setup.
- Sprint 2 provides the repair engine that takes a trapped API failure and
  returns a structured repair for payload drift, route drift, or auth drift.
- Sprint 4 wraps the repair engine with a mutable environment, benchmark loop,
  reward scoring, and training-facing dataset pipeline.

## Why This Repo Exists

The project is built from the product direction captured in
`from_gpt_context.txt`. The goal is to move from a believable repair module to
an end-to-end API self-healing system with benchmarking and training-ready
artifacts.

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

## What The Repo Delivers Now

- Sprint 1 live FastAPI mock server and fuzzing foundation
- Sprint 2 typed request, response, diagnostics, schema, and proxy-contract models
- local OpenAPI loading plus multi-source docs-fetch scaffolding
- schema extraction with route matching, confidence, ranked candidates, and auth parsing
- deterministic repair strategies for payload, route, auth, and combined drift
- optional model refinement with safe fallback on invalid model output
- proxy-facing adapter and retry orchestration
- persistent telemetry and reusable repair cache
- Sprint 4 mutable environment, benchmark loop, and reward scoring
- training-facing episode formatting and TRL-ready dataset preparation

## What This Repo Does Not Yet Claim

- not a fully trained production RL policy
- not final OpenEnv deployment as the only runtime mode
- not final judge-facing model-improvement proof across large unseen scenario sets

Those pieces come after the benchmark and dataset pipeline are validated.

## Stable Repair Contract

Sprint 2 should be treated as the stable repair component:

- input: `TrappedError`
- output: `HealedRequest`
- primary callable: `app.main.process_trapped_error()`

For safer orchestration and explicit failure reasons, integrations can also use:

- `app.main.process_trapped_error_safe()`
- `app.services.proxy_adapter.handle_proxy_failure()`
- `app.services.proxy_adapter.handle_proxy_failure_with_retry()`

## Current Runtime Flow

1. A proxy or test harness traps an upstream API failure.
2. ReMorph loads the relevant docs or spec bundle.
3. ReMorph extracts the best endpoint contract with explainable route matching.
4. ReMorph builds a repair context and prepares a deterministic baseline.
5. The model may refine the repair if configured.
6. ReMorph returns a structured healed request with diagnostics.
7. Sprint 4 can benchmark the repair, score reward, and format training data.

## Demo Strength

The current local baseline is strong enough to show the three core cases:

- Scenario A: payload rewritten into the nested `user` schema
- Scenario B: route migrated to `/api/v2/finance/ledger` and auth rewritten
- Scenario C: bearer auth converted into `x-api-key`

## Sprint 4 Benchmark And Training Flow

Sprint 4 adds:

- local and live environment modes
- a simulated, live FastAPI, or OpenEnv-style backend
- baseline vs adaptive benchmark runs
- deterministic reward scoring
- cache-aware benchmark modes
- training/eval JSONL generation from benchmark episodes
- TRL-ready prompt/completion dataset preparation
- a Phase 1 dataset adapter for `training_dataset.json`

Typical local flow:

```bash
.venv/bin/python scripts/run_benchmark.py --episodes-per-scenario 3 --output-dir runtime/sprint4_clean --cache-mode clear --disable-telemetry
.venv/bin/python scripts/generate_sprint4_dataset.py --episodes-path runtime/sprint4_clean/episodes.jsonl --output-dir runtime/sprint4_clean/dataset --eval-ratio 0.2
.venv/bin/python -m sprint4.training.trl_train_grpo --episodes-path runtime/sprint4_clean/episodes.jsonl --output-dir runtime/sprint4_clean/training --eval-ratio 0.2
```

Live benchmark flow:

```bash
.venv/bin/python -m uvicorn server.main:app --reload
.venv/bin/python scripts/run_benchmark.py --env-mode live --live-base-url http://127.0.0.1:8000 --episodes-per-scenario 1 --output-dir runtime/sprint4_live --cache-mode disable --disable-telemetry
```

Run every raw Sprint 1 live scenario:

```bash
.venv/bin/python scripts/run_benchmark.py --env-mode live --live-base-url http://127.0.0.1:8000 --live-scenario-selection all --episodes-per-scenario 1 --output-dir runtime/sprint4_live_all --cache-mode disable --disable-telemetry
```

Representative live auth now defaults to `auth_missing_tenant`, because that
case is repairable from the contract. If you want to benchmark the harder
unrecoverable case, run `--live-raw-scenario auth_missing_token`.

Top-level summaries use broad categories:

- `payload_drift`
- `route_drift`
- `auth_drift`

Exact Sprint 1 labels are preserved as `raw_scenario_type` inside
`episodes.jsonl` and `benchmark_report.json`.

## Sprint 1 Setup

Jenish's Sprint 1 work is the setup for the live mock-server and chaos-gym
foundation.

### Sprint 1 Requirements

Install the ecosystem dependencies first:

```bash
pip install -r requirements.txt
```

If you are using a virtual environment, activate it before running the server
or generator.

### Sprint 1 Run Order

1. Boot the live target server:

```bash
uvicorn server.main:app --reload
```

The server starts on `http://127.0.0.1:8000`.

2. Export or review the OpenAPI contract:

```bash
python server/export_openapi.py
```

or

```bash
python3 -m server.export_openapi
```

3. Run the universal dataset generator:

```bash
python dataset_generator.py -m 1
python dataset_generator.py -m 10
```

### Sprint 1 Swagger Setup

With the server running, open:

```text
http://127.0.0.1:8000/docs
```

To authorize in Swagger, paste this JWT into the `HTTPBearer` authorize box:

```text
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZnV6emVyX2FnZW50XzAwNyIsInJvbGUiOiJhZG1pbiJ9.UuceJXhdiSBpwb47N1MffwuX3vd8KFwvtNYZP8wVTTo
```

For the sample `POST /api/v1/payments/process` route, use:

- `x-api-key: secret`
- `x-vendor-id: ven-123`

and this baseline payload:

```json
{
  "amount": 100.50,
  "currency": "USD",
  "card_details": {
    "card_number": "1234567812345678",
    "cvv": "123",
    "expiry": "12/26"
  },
  "billing_address": {
    "street": "123 Wall St",
    "zip_code": "10005",
    "iso_country": "US"
  }
}
```

### Sprint 1 Dataset Intent

The Sprint 1 generator produces `training_dataset.json`, which logs valid and
failing requests against the live mock server. That dataset is the Phase 1
chaos-gym output that later repair and RL layers can build on.

## Repository Layout

- `app/`: main repair engine package
- `server/`: Sprint 1 live mock server and API target
- `specs/`: exported OpenAPI contracts used by the fuzzer and integrations
- `sprint4/`: benchmark, environment, rewards, evaluation, and training helpers
- `scripts/`: local demo, benchmark, and dataset-generation entrypoints
- `tests/`: automated coverage for repair logic, benchmark flow, and training prep
- `docs/context/`: runbooks, contracts, project notes, and handoff docs
- `docs/changes/`: change log for repo-level traceability
- `docs/journal/`: implementation notes with what changed and why
- `runtime/`: generated cache, telemetry, benchmark, and training artifacts

## Team Ownership

- `Jenish`: Sprint 1 proxy / transport layer and live mock-server foundation
- `Vedant`: Sprint 2 repair engine and Sprint 4 system integration
- `Sachin`: Sprint 3 support across environment, training, and evaluation delivery

## Change Tracking Rule

Every code edit should ship with a documentation update. The working agreement
for that process lives in [docs/context/change-management.md](/home/matter/Documents/ReMorph/docs/context/change-management.md).

## Runbook And Handoffs

- run and validation guide: [docs/context/run-and-test-guide.md](/home/matter/Documents/ReMorph/docs/context/run-and-test-guide.md)
- proxy contract for Jenish: [docs/context/jenish-proxy-contract.md](/home/matter/Documents/ReMorph/docs/context/jenish-proxy-contract.md)
- training and reward handoff for Sachin: [docs/context/sachin-training-handoff.md](/home/matter/Documents/ReMorph/docs/context/sachin-training-handoff.md)
