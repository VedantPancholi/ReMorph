# Training Plan

## Objective
Use benchmark episodes as a reward-labeled dataset to demonstrate policy improvement loops in a hackathon environment.

## Inputs
- `runtime/sprint4/episodes.jsonl`
- reward and outcome labels from Sprint 4 execution

## Scripts
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

## Recommended Production Pattern
- Keep OpenEnv runtime and training jobs separate.
- Generate episodes with `scripts/run_benchmark.py`.
- Freeze JSONL datasets by date/version before GRPO runs.
- Track run metadata (model, prompt version, reward config, commit SHA) with each training artifact.
