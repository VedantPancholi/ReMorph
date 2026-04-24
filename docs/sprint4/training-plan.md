# Training Plan

## Objective
Use benchmark episodes as a reward-labeled dataset to demonstrate policy improvement loops in a hackathon environment.

## RL-Ready Benchmark Contract

Before RL training, Sprint 4 freezes the live benchmark into two slices:

- Repairable slice:
  - `schema_missing_key`
  - `schema_type_coercion`
  - `schema_extra_key`
  - `schema_null_injection`
  - `route_regression`
  - `route_method_spoof`
  - `route_invalid_path`
  - `auth_missing_tenant`
- Unrecoverable slice:
  - `auth_missing_token`
  - `auth_malformed_jwt`

Why we freeze this contract:

- the policy objective stays clean: recover what is recoverable
- unrecoverable auth failures stay available as abstention and fail-safe negatives
- reward interpretation becomes more trustworthy because we stop mixing policy misses with impossible repairs

Training default:

- generate GRPO/TRL datasets from the `repairable` partition
- keep `unrecoverable` scenarios for offline eval, abstention shaping, or a later safe-failure objective

## Inputs
- `runtime/sprint4/episodes.jsonl`
- reward and outcome labels from Sprint 4 execution

## Scripts
- `scripts/run_benchmark.py`
- `scripts/generate_sprint4_dataset.py`
- `sprint4/training/trl_train_grpo.py`
- `sprint4/training/unsloth_train_grpo.py`

## Install
```bash
pip install -r requirements/training.txt
```

## Scope
- These scripts are intentionally lightweight and optional.
- They do not block core Sprint 4 runtime.
- They produce summary artifacts and define integration points for full GRPO training pipelines.

## Current Training Prep Flow

1. Run the benchmark loop and write `runtime/sprint4/episodes.jsonl`.
2. Choose a cache mode with `scripts/run_benchmark.py --cache-mode reuse|clear|disable`.
3. Convert adaptive episodes into train/eval JSONL files with `scripts/generate_sprint4_dataset.py`.
4. Freeze the repo-native pre-training scoreboard with `scripts/freeze_sprint4_scoreboard.py`.
5. Inspect the frozen shared eval manifest plus the failure-analysis summary.
6. Only then move to supervised warm-start training.
7. Run `sprint4/training/trl_train_grpo.py` or `sprint4/training/unsloth_train_grpo.py` after the warm-start path is established.

Dataset generation example:

```bash
python scripts/generate_sprint4_dataset.py \
  --episodes-path runtime/sprint4_live_all/episodes.jsonl \
  --output-dir runtime/sprint4_live_all/dataset_repairable \
  --benchmark-partition repairable
```

Pre-training scoreboard freeze example:

```bash
python scripts/freeze_sprint4_scoreboard.py \
  --episodes-path runtime/pre_rl_live_all_hardened_v3/episodes.jsonl \
  --output-dir artifacts/sprint4/eval/pretraining_scoreboard \
  --benchmark-partition all
```

The freeze step persists:

- canonical manifests, including the shared eval manifest
- baseline real-run eval artifacts
- adaptive real-run eval artifacts
- one machine-readable comparison artifact
- one failure-analysis summary for training focus

## Current Decision Rule

Do not start GRPO first.

The preferred order is:

1. Freeze the first repo-native pre-training scoreboard.
2. Review failure analysis and safety behavior on the frozen eval set.
3. Train a supervised warm-start policy on canonical `SupervisedRow` data.
4. Evaluate the warm-started policy on the same frozen shared eval manifest.
5. Add reward-guided refinement only if it still buys measurable improvement.

## Supervised Warm-Start

Files:

- `sprint4/training/supervised_warmstart.py`
- `scripts/train_sprint4_supervised.py`

Current learned-policy checkpoint:

- shared eval manifest id: `c6cc003f9220869e`
- baseline overall success: `0.30`
- adaptive overall success: `1.00`
- warm-start overall success: `0.50`
- warm-start repairable success: `0.375`
- warm-start correct abstention: `1.00`
- warm-start average reward: `0.7`

Current interpretation:

- the learned policy closes part of the gap vs adaptive
- abstention behavior on unrecoverable auth stays clean
- the main remaining weaknesses are repairable route/payload/auth slices
- this is a credible place to decide whether reward-guided refinement is worth the extra complexity

Current targeted refinement inputs:

- error analysis artifacts live under:
  - `artifacts/sprint4/training/supervised_warmstart/error_analysis/`
- main misses:
  - `route_regression`
  - `auth_missing_tenant`
  - `schema_type_coercion`
  - `route_method_spoof`
  - `schema_missing_key`
- important confusion:
  - `repair_auth -> repair_payload`
- leakage guard:
  - the warm-start pipeline now raises if `group_id` overlap exists between the
    supervised train manifest and the frozen shared eval manifest

Targeted refinement status:

- `sprint4/training/targeted_refinement.py` now builds deterministic refinement
  candidates from the error-analysis artifacts
- `scripts/refine_sprint4_warmstart.py` evaluates the candidate on the same
  frozen shared eval manifest
- promotion is gated:
  - a refinement candidate is only recommended if it beats the frozen
    warm-start checkpoint without regressing abstention safety
- current heuristic refinement candidate is **not promoted**
  - recommended policy remains `warmstart`
  - this keeps the repo honest while still giving us a reusable refinement loop

Warm-start command:

```bash
python scripts/train_sprint4_supervised.py \
  --supervised-rows-path artifacts/sprint4/eval/pretraining_scoreboard/data/supervised_rows.jsonl \
  --supervised-train-manifest-path artifacts/sprint4/eval/pretraining_scoreboard/manifests/supervised_train_manifest.json \
  --shared-eval-manifest-path artifacts/sprint4/eval/pretraining_scoreboard/manifests/shared_eval_manifest.json \
  --transition-rows-path artifacts/sprint4/eval/pretraining_scoreboard/data/adaptive_transition_rows.jsonl \
  --baseline-summary-path artifacts/sprint4/eval/pretraining_scoreboard/baseline_real/summary.json \
  --adaptive-summary-path artifacts/sprint4/eval/pretraining_scoreboard/adaptive_real/summary.json \
  --output-dir artifacts/sprint4/training/supervised_warmstart
```

## Dataset Shape

Each generated row includes:

- `prompt`: a contract-grounded repair prompt
- `completion`: the target repair action as JSON
- `reward`: the episode reward
- `state`: failed request, error context, retry count, and selected contract slice
- `action`: fixed method, URL, payload, headers, and repair type
- `metadata`: scenario type, raw scenario type, benchmark partition, cache/LLM hints, and source paths

## Recommended Production Pattern
- Keep OpenEnv runtime and training jobs separate.
- Generate episodes with `scripts/run_benchmark.py`.
- Freeze JSONL datasets by date/version before GRPO runs.
- Track run metadata (model, prompt version, reward config, commit SHA) with each training artifact.
