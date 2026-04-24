# ReMorph

ReMorph is an API self-healing project built in layers:

- `app/`: Sprint 2 repair brain
- `sprint4/`: benchmark, reward, training, and evaluation pipeline
- `target_api/`: live FastAPI target server, OpenAPI export, and dataset generation
- `remorph_client/`: product-style self-healing API client wrapper

The repo now supports two main runtime modes:

- `local`: deterministic in-memory benchmark for fast validation
- `live`: real HTTP calls against the Target API FastAPI server

At a high level, ReMorph works like this:

1. an API request fails
2. ReMorph traps the failure and inspects the contract
3. it repairs recoverable payload, route, or auth drift
4. it retries the request
5. it safely abstains on unrecoverable credential failures

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
- `remorph_client/`
  Product-facing wrapper for self-healing API requests.

## Install

Create the environment and install development dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements/dev.txt
cp .env.example .env
```

If you want training/OpenEnv extras:

```bash
.venv/bin/python -m pip install -r requirements/training.txt
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

Generate RL-facing train/eval JSONL:

```bash
.venv/bin/python -m sprint4.training.episode_dataset \
  --episodes-path runtime/sprint4_local/episodes.jsonl \
  --output-dir runtime/sprint4_local/rl_dataset \
  --split all
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

## Large-Scale Training Pipeline

Generate many repairable and unrecoverable episodes with the existing Sprint 4
workflow runner:

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

Format those episodes into compact TRL-ready prompt/target rows:

```bash
.venv/bin/python -m sprint4.training.trl_sample_formatter \
  --episodes-path runtime/training_large/episodes.jsonl \
  --output-dir runtime/training_large/trl_dataset \
  --eval-ratio 0.2 \
  --seed 42
```

Train the lightweight HF TRL-compatible repair-policy pipeline:

```bash
.venv/bin/python -m sprint4.training.trl_train_grpo \
  --train-path runtime/training_large/trl_dataset/train_prompts.jsonl \
  --eval-path runtime/training_large/trl_dataset/eval_prompts.jsonl \
  --output-dir runtime/training_large/trl_training \
  --model-name sshleifer/tiny-gpt2
```

This writes:

- `training_metrics.json`
- `reward_curve.json`
- `reward_curve.png`
- `warnings.json`
- `trained_policy_model.json`
- `trained_policy_summary.json`
- `trained_policy_eval.json`
- `trained_policy_eval.md`

Evaluate and compare the trained policy:

```bash
.venv/bin/python -m sprint4.evaluation.evaluate_trained_policy \
  --eval-path runtime/training_large/trl_dataset/eval_prompts.jsonl \
  --output-dir runtime/training_large/trl_training \
  --model-path runtime/training_large/trl_training/trained_policy_model.json

.venv/bin/python -m sprint4.evaluation.compare_trained_vs_untrained \
  --input-dir runtime/training_large/trl_dataset \
  --output-dir runtime/training_large/comparison \
  --trained-policy-summary-path runtime/training_large/trl_training/trained_policy_summary.json
```

Current training behavior is intentionally honest:

- ReMorph still keeps deterministic repair, schema extraction, and runtime retry
  validation in the loop.
- Safe abstention remains a first-class action for unrecoverable auth failures.
- When full GRPO execution is impractical, the pipeline falls back to a
  lightweight TRL-compatible structured policy learner and labels that mode
  explicitly in the training summary.

If TRL is not installed, install optional training dependencies with:

```bash
.venv/bin/python -m pip install -r requirements/training.txt
```

For Google Colab, use:

- [Large Training Script](notebooks/remorph_hf_trl_large_training.py)
- [Minimal TRL Script](notebooks/remorph_trl_colab.py)

## ReMorphClient

Use ReMorph as a product-like self-healing API layer:

```python
from remorph_client import ReMorphClient

client = ReMorphClient.from_config("examples/remorph.yaml")
response = client.request(
    method="POST",
    path="/users",
    json={"first_name": "John", "last_name": "Doe"},
)
```

The example config lives at:

- [remorph.yaml](examples/remorph.yaml)

`ReMorphClient` supports:

- `base_url`
- `openapi_spec_path`
- auth headers
- `safe_mode`
- `max_retries`

Safe mode means the client will emit `safe_abstain` instead of inventing
missing or malformed credentials.

## Final Package

Submission-ready evidence is available under:

- [Sprint 4 Final Clean Package](runtime/sprint4_final_clean/package/README.md)

That package includes:

- repairable benchmark artifacts
- unrecoverable auth artifacts
- dataset summaries
- comparison reports
- a final scoreboard

The larger training pipeline can also generate:

- `runtime/training_large/episode_generation_summary.json`
- `runtime/training_large/trl_dataset/trl_dataset_summary.json`
- `runtime/training_large/trl_training/training_metrics.json`
- `runtime/training_large/trl_training/reward_curve.json`
- `runtime/training_large/trl_training/reward_curve.png`
- `runtime/training_large/trl_training/trained_policy_eval.json`
- `runtime/training_large/trl_training/trained_policy_eval.md`

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
- [RL-Facing Layer](sprint4/docs/rl-facing-layer.md)
- [Mini Blog](docs/submission/mini_blog.md)
- [Two Minute Video Script](docs/submission/two_min_video_script.md)
- [Three Minute Pitch](docs/submission/three_min_pitch.md)
