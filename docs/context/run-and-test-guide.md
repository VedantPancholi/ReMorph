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
.venv/bin/python -m pip install -r requirements/training.txt
```

Important:

- Prefer `.venv/bin/python -m pytest` over `.venv/bin/pytest` in this workspace.
- Prefer `.venv/bin/python -m pip` over `.venv/bin/pip` in this workspace if
  the pip launcher has a stale shebang.
- Reward-curve export requires `matplotlib`, which is included in
  `requirements/training.txt`.
- TRL-style training is optional and is not required for the normal Sprint 4
  benchmark or dataset flows.

## Repo Map

- `app/`: Sprint 2 repair brain
- `sprint4/`: benchmark, environment adapters, rewards, evaluation, training prep
- `target_api/`: live FastAPI target, spec export, and dataset generation
- `runtime/`: disposable generated outputs
- `examples/artifacts/`: tracked sample outputs

## Fastest Verification

```bash
.venv/bin/python -m pytest -q
.venv/bin/python run_local_test.py --mode smoke --scenario a
.venv/bin/python run_local_test.py --mode heal --scenario a
```

## Local Sprint 4 Benchmark

```bash
.venv/bin/python scripts/run_benchmark.py \
  --backend simulated \
  --env-mode local \
  --episodes-per-scenario 3 \
  --output-dir runtime/sprint4_local \
  --cache-mode clear \
  --disable-telemetry
```

Generate the RL-facing dataset from benchmark episodes:

```bash
.venv/bin/python -m sprint4.training.episode_dataset \
  --episodes-path runtime/sprint4_local/episodes.jsonl \
  --output-dir runtime/sprint4_local/dataset \
  --split all
```

Generate the comparison report for baseline, adaptive rules, and the trained
policy placeholder:

```bash
.venv/bin/python -m sprint4.evaluation.compare_trained_vs_untrained \
  --input-dir runtime/sprint4_local/dataset \
  --output-dir runtime/sprint4_local/comparison
```

Current clean final-package equivalents live under:

- `runtime/sprint4_final_clean/local/`
- `runtime/sprint4_final_clean/training_dataset/`
- `runtime/sprint4_final_clean/comparison/`

## Clean Final Evidence Run

Repairable slice:

```bash
.venv/bin/python scripts/run_benchmark.py \
  --backend simulated \
  --env-mode local \
  --output-dir runtime/sprint4_final_clean/local \
  --cache-mode clear \
  --disable-telemetry
```

```bash
.venv/bin/python -m sprint4.training.episode_dataset \
  --episodes-path runtime/sprint4_final_clean/local/episodes.jsonl \
  --output-dir runtime/sprint4_final_clean/training_dataset \
  --split all
```

```bash
.venv/bin/python -m sprint4.evaluation.compare_trained_vs_untrained \
  --input-dir runtime/sprint4_final_clean/training_dataset \
  --output-dir runtime/sprint4_final_clean/comparison
```

Unrecoverable auth slice used by the final package:

```bash
.venv/bin/python -c "from sprint4.env.scenario_loader import load_contract_bundle, ScenarioRequest; from sprint4.evaluation.benchmark_runner import run_benchmark; bundle=load_contract_bundle(); scenarios=[ScenarioRequest(scenario_type='auth_drift', raw_scenario_type='auth_missing_token', drift_mode='auth', method='GET', url='https://mock.example.com/api/v2/finance/ledger', headers={}, payload=None, local_spec_path=bundle.drift_paths['auth']), ScenarioRequest(scenario_type='auth_drift', raw_scenario_type='auth_malformed_jwt', drift_mode='auth', method='GET', url='https://mock.example.com/api/v2/finance/ledger', headers={'Authorization':'Bearer malformed.jwt.token'}, payload=None, local_spec_path=bundle.drift_paths['auth'])]; run_benchmark(bundle=bundle, scenarios=scenarios, episodes_per_scenario=1, output_dir='runtime/sprint4_final_clean/unrecoverable_auth', backend='simulated')"
```

```bash
.venv/bin/python -m sprint4.training.episode_dataset \
  --episodes-path runtime/sprint4_final_clean/unrecoverable_auth/episodes.jsonl \
  --output-dir runtime/sprint4_final_clean/unrecoverable_auth_dataset \
  --split all
```

```bash
.venv/bin/python -m sprint4.evaluation.compare_trained_vs_untrained \
  --input-dir runtime/sprint4_final_clean/unrecoverable_auth_dataset \
  --output-dir runtime/sprint4_final_clean/unrecoverable_auth_comparison
```

## Live Target API Benchmark

Start the live server:

```bash
.venv/bin/python -m uvicorn target_api.server.main:app --reload --host 127.0.0.1 --port 8000
```

Run the representative live benchmark:

```bash
.venv/bin/python scripts/run_benchmark.py \
  --backend live \
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
  --backend live \
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
.venv/bin/python -m sprint4.training.episode_dataset \
  --episodes-path runtime/sprint4_live_all/episodes.jsonl \
  --output-dir runtime/sprint4_live_all/dataset_repairable \
  --split all \
  --filter repairable_only
```

Run one exact raw scenario:

```bash
.venv/bin/python scripts/run_benchmark.py \
  --backend live \
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

## Optional TRL Training

Run the optional training scaffold on the clean repairable dataset:

```bash
.venv/bin/python -m sprint4.training.trl_train_grpo \
  --train-path runtime/sprint4_final_clean/training_dataset/train.jsonl \
  --eval-path runtime/sprint4_final_clean/training_dataset/eval.jsonl \
  --output-dir runtime/sprint4_final_clean/trl_training \
  --model-name sshleifer/tiny-gpt2
```

This writes:

- `training_metrics.json`
- `reward_curve.json`
- `reward_curve.png`
- `trained_policy_summary.json`

Then generate the trained-vs-untrained comparison:

```bash
.venv/bin/python -m sprint4.evaluation.compare_trained_vs_untrained \
  --input-dir runtime/sprint4_final_clean/training_dataset \
  --output-dir runtime/sprint4_final_clean/comparison \
  --trained-policy-summary-path runtime/sprint4_final_clean/trl_training/trained_policy_summary.json
```

If the training command fails with `ModuleNotFoundError: matplotlib`, install:

```bash
.venv/bin/pip install -r requirements/training.txt
```

If your environment blocks package downloads, the benchmark, dataset, and
comparison pipeline still works without the optional reward-curve and TRL step.

## Large Training Pipeline

Generate many adaptive episodes across repairable and unrecoverable benchmark
scenarios:

```bash
.venv/bin/python scripts/generate_training_episodes.py \
  --episodes 1000 \
  --output runtime/training_large/episodes.jsonl \
  --cache-mode disable \
  --include-repairable \
  --include-unrecoverable \
  --seed 42 \
  --backend simulated \
  --env-mode local
```

This writes:

- `runtime/training_large/episodes.jsonl`
- `runtime/training_large/episode_generation_summary.json`

Format TRL-ready prompt rows:

```bash
.venv/bin/python -m sprint4.training.trl_sample_formatter \
  --episodes-path runtime/training_large/episodes.jsonl \
  --output-dir runtime/training_large/trl_dataset \
  --eval-ratio 0.2 \
  --seed 42
```

This writes:

- `train_prompts.jsonl`
- `eval_prompts.jsonl`
- `trl_dataset_summary.json`

Run the larger HF TRL-compatible structured policy training flow:

```bash
.venv/bin/python -m sprint4.training.trl_train_grpo \
  --train-path runtime/training_large/trl_dataset/train_prompts.jsonl \
  --eval-path runtime/training_large/trl_dataset/eval_prompts.jsonl \
  --output-dir runtime/training_large/trl_training \
  --model-name sshleifer/tiny-gpt2 \
  --max-steps 50 \
  --batch-size 2 \
  --learning-rate 5e-5
```

This writes:

- `trained_policy_model.json`
- `training_metrics.json`
- `reward_curve.json`
- `reward_curve.png`
- `warnings.json`
- `trained_policy_summary.json`
- `trained_policy_eval.json`
- `trained_policy_eval.md`

Generate the honest large-run comparison:

```bash
.venv/bin/python -m sprint4.evaluation.compare_trained_vs_untrained \
  --input-dir runtime/training_large/trl_dataset \
  --output-dir runtime/training_large/comparison \
  --trained-policy-summary-path runtime/training_large/trl_training/trained_policy_summary.json
```

Important:

- `compare_trained_vs_untrained` now supports TRL prompt datasets directly.
- `--trained-policy-summary-path` belongs to the comparison command, not the
  training command.
- `trl_sample_formatter` now fails fast if the episode file is missing or empty,
  instead of silently creating a zero-row dataset.

Current large-run result from `runtime/training_large/`:

- total generated episodes: `1000`
- repairable count: `800`
- unrecoverable count: `200`
- adaptive rules: success `1.0000`, avg reward `1.3000`
- trained policy: success `1.0000`, avg reward `1.2600`

Interpretation:

- the larger training pipeline is working end to end
- safe abstention is preserved
- the current trained policy is close, but it does not beat adaptive rules yet

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
