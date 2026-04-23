# Training Plan

## Objective
Use benchmark episodes as a reward-labeled dataset to demonstrate policy improvement loops in a hackathon environment.

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
pip install -r requirements.txt
pip install -r requirements-sprint4.txt
```

## Scope
- These scripts are intentionally lightweight and optional.
- They do not block core Sprint 4 runtime.
- They produce summary artifacts and define integration points for full GRPO training pipelines.

## Current Training Prep Flow

1. Run the benchmark loop and write `runtime/sprint4/episodes.jsonl`.
2. Choose a cache mode with `scripts/run_benchmark.py --cache-mode reuse|clear|disable`.
3. Convert adaptive episodes into train/eval JSONL files with `scripts/generate_sprint4_dataset.py`.
4. Run `sprint4/training/trl_train_grpo.py` or `sprint4/training/unsloth_train_grpo.py`.
5. Inspect the generated dataset manifest plus offline eval summary before wiring a full GRPO trainer.

## Dataset Shape

Each generated row includes:

- `prompt`: a contract-grounded repair prompt
- `completion`: the target repair action as JSON
- `reward`: the episode reward
- `state`: failed request, error context, retry count, and selected contract slice
- `action`: fixed method, URL, payload, headers, and repair type
- `metadata`: scenario type, cache/LLM hints, and source paths

## Recommended Production Pattern
- Keep OpenEnv runtime and training jobs separate.
- Generate episodes with `scripts/run_benchmark.py`.
- Freeze JSONL datasets by date/version before GRPO runs.
- Track run metadata (model, prompt version, reward config, commit SHA) with each training artifact.
