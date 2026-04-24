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

Freeze the RL-ready repairable dataset slice from benchmark episodes:

```bash
.venv/bin/python scripts/generate_sprint4_dataset.py \
  --episodes-path runtime/sprint4_live_all/episodes.jsonl \
  --output-dir runtime/sprint4_live_all/dataset_repairable \
  --benchmark-partition repairable
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

Frozen RL-ready benchmark contract:

- Repairable raw scenarios:
  - `schema_missing_key`
  - `schema_type_coercion`
  - `schema_extra_key`
  - `schema_null_injection`
  - `route_regression`
  - `route_method_spoof`
  - `route_invalid_path`
  - `auth_missing_tenant`
- Unrecoverable raw scenarios:
  - `auth_missing_token`
  - `auth_malformed_jwt`

Training default should use the repairable slice. Unrecoverable auth cases are
best kept for abstention/fail-safe evaluation rather than the main repair policy
objective.

## Freeze The Pre-Training Scoreboard

Freeze the first repo-native baseline-vs-adaptive scoreboard from real benchmark
episodes:

```bash
.venv/bin/python scripts/freeze_sprint4_scoreboard.py \
  --episodes-path runtime/pre_rl_live_all_hardened_v3/episodes.jsonl \
  --output-dir artifacts/sprint4/eval/pretraining_scoreboard \
  --benchmark-partition all \
  --seed 42 \
  --eval-ratio 0.2
```

This writes:

- canonical manifests under `artifacts/sprint4/eval/pretraining_scoreboard/manifests/`
- frozen baseline and adaptive eval runs under:
  - `artifacts/sprint4/eval/pretraining_scoreboard/baseline_real/`
  - `artifacts/sprint4/eval/pretraining_scoreboard/adaptive_real/`
- shared comparison artifacts under `artifacts/sprint4/eval/pretraining_scoreboard/comparisons/`
- checkpoint and failure-analysis summaries under `artifacts/sprint4/eval/pretraining_scoreboard/checkpoint/`

Important:

- the shared eval manifest is frozen once and reused unchanged for baseline,
  adaptive, and later trained-policy comparisons
- grouping now fingerprints the failed scenario itself, so the same underlying
  case stays aligned across baseline and adaptive even if request ids differ
- this checkpoint should be treated as the official pre-training reference, not
  mixed with earlier synthetic validation outputs

## Train The Supervised Warm-Start Policy

Train the first learned policy on the frozen supervised train manifest and
evaluate it on the same shared eval manifest:

```bash
.venv/bin/python scripts/train_sprint4_supervised.py \
  --supervised-rows-path artifacts/sprint4/eval/pretraining_scoreboard/data/supervised_rows.jsonl \
  --supervised-train-manifest-path artifacts/sprint4/eval/pretraining_scoreboard/manifests/supervised_train_manifest.json \
  --shared-eval-manifest-path artifacts/sprint4/eval/pretraining_scoreboard/manifests/shared_eval_manifest.json \
  --transition-rows-path artifacts/sprint4/eval/pretraining_scoreboard/data/adaptive_transition_rows.jsonl \
  --baseline-summary-path artifacts/sprint4/eval/pretraining_scoreboard/baseline_real/summary.json \
  --adaptive-summary-path artifacts/sprint4/eval/pretraining_scoreboard/adaptive_real/summary.json \
  --output-dir artifacts/sprint4/training/supervised_warmstart
```

This writes:

- `model_artifact.json`
- `training_summary.json`
- `eval_on_shared_manifest.json`
- `comparison_vs_pretraining.json`
- `comparison_vs_pretraining.md`

Current frozen warm-start checkpoint:

- shared eval manifest id: `c6cc003f9220869e`
- baseline overall success: `0.30`
- adaptive overall success: `1.00`
- warm-start overall success: `0.50`
- warm-start repairable success: `0.375`
- warm-start correct abstention: `1.00`

Interpretation:

- the first learned policy already improves over baseline on the frozen eval set
- adaptive still remains the best policy
- the remaining gap is concentrated in repairable payload/auth/route slices and
  is a better target for later refinement than jumping straight into RL

Analyze warm-start vs adaptive errors on the same frozen shared eval manifest:

```bash
.venv/bin/python scripts/analyze_sprint4_policy_errors.py \
  --model-artifact-path artifacts/sprint4/training/supervised_warmstart/model_artifact.json \
  --supervised-train-manifest-path artifacts/sprint4/eval/pretraining_scoreboard/manifests/supervised_train_manifest.json \
  --shared-eval-manifest-path artifacts/sprint4/eval/pretraining_scoreboard/manifests/shared_eval_manifest.json \
  --transition-rows-path artifacts/sprint4/eval/pretraining_scoreboard/data/adaptive_transition_rows.jsonl \
  --warmstart-eval-path artifacts/sprint4/training/supervised_warmstart/eval_on_shared_manifest.json \
  --adaptive-eval-path artifacts/sprint4/eval/pretraining_scoreboard/adaptive_real/eval_results.jsonl \
  --output-dir artifacts/sprint4/training/supervised_warmstart/error_analysis
```

This writes:

- `warmstart_error_analysis.json`
- `warmstart_error_analysis.md`
- `missed_by_scenario.json`
- `action_confusion.json`

Current analysis highlights:

- no train/eval leakage is allowed: the warm-start pipeline now asserts there is
  no `group_id` overlap between the supervised train manifest and shared eval manifest
- largest reward gap: `route_regression`
- main action confusion: `repair_auth -> repair_payload`
- no unsafe auth hallucinations on the frozen eval set

Run targeted refinement without changing the frozen eval contract:

```bash
.venv/bin/python scripts/refine_sprint4_warmstart.py \
  --output-dir artifacts/sprint4/training/supervised_warmstart_refined_validation3
```

This writes:

- `refinement_plan.json`
- `model_artifact.json`
- `eval_on_shared_manifest.json`
- `comparison_vs_warmstart.json`
- `comparison_vs_warmstart.md`
- `adoption_decision.json`

Current refinement checkpoint:

- the first heuristic refinement candidate is not promoted
- `adoption_decision.json` recommends staying on `warmstart`
- this is intentional: the refinement loop is implemented, but promotion is
  now gated by real shared-eval improvement instead of optimism

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
