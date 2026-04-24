# Sprint 4 Architecture

## Goal
Sprint 4 wraps the frozen Sprint 2 repair brain with an end-to-end self-healing loop:

1. Mutable environment loads baseline contract
2. Drift engine mutates contract
3. Proxy sends original request
4. Environment returns failure
5. Proxy packages `TrappedError`
6. Sprint 2 `process_trapped_error()` runs repair
7. Proxy retries healed request
8. Environment returns success/failure
9. Reward function scores episode
10. Episode logger writes JSONL metrics
11. Policy adapter converts episode traces into RL-facing transitions
12. Evaluation compares baseline vs adaptive vs trained-policy placeholder

## Modules
- `sprint4/env/`: backend interface, simulated mutable API env, live FastAPI adapter, OpenEnv adapter, drift modes, live failure parsing
- `sprint4/proxy/`: execution, trap/repair handoff, retry workflow, episode logging
- `sprint4/rewards/`: deterministic reward scoring with explicit component breakdown
- `sprint4/evaluation/`: benchmark, package artifacts, comparison, and reward-curve generation
- `sprint4/training/`: policy adapter, episode dataset export, and optional TRL scaffold
- `remorph_client/`: product-facing client wrapper around the same safe repair workflow

## Integration Contract
- Sprint 2 remains unchanged.
- Sprint 4 only calls:
  - `app.main.process_trapped_error()`
- Sprint 4 passes drift-specific contract path via `local_spec_path`.
- Sprint 4 may also produce `safe_abstain` instead of a synthetic repair when
  credential material is missing or invalid.

## Environment Modes
- `local`: uses the `simulated` backend for deterministic in-memory drift tests.
- `live`: uses the Sprint 1 FastAPI target server over HTTP.
- live spec and dataset now live under `target_api/`.

## Environment Backends
- `simulated` (default backend for `local` mode): deterministic in-memory env for local development and CI.
- `live`: HTTP adapter around the Sprint 1 FastAPI target server.
- `openenv`: production-facing adapter that uses OpenEnv client `reset()`, `step()`, and `state()` APIs.

## Recovery Outcome Types

Sprint 4 now distinguishes between repairable and unrecoverable outcomes:

- successful repair and retry
- failed repair attempt
- wrong-route or hallucinated repair penalty paths
- explicit safe abstention for unrecoverable auth cases

The canonical unrecoverable auth outcome is:

- `healing_action = "safe_abstain"`
- `recoverable = false`
- `unrecoverable_reason = "missing_or_invalid_credential_material"`

This keeps the system from inventing fake tokens or pretending to repair
missing credentials from thin air.

## Reward Breakdown

The reward layer now exposes both the total reward and structured components:

- `success_reward`
- `one_cycle_bonus`
- `retry_penalty`
- `wrong_route_penalty`
- `hallucination_penalty`
- `safe_abstention_bonus`
- `unrecoverable_penalty`
- `final_reward`

This richer breakdown is what feeds both artifact explainability and
training-facing dataset export.

## RL-Facing Layer

Sprint 4 now includes a thin RL-facing translation layer above the benchmark
runtime:

- `policy_adapter.py` converts episode records into:
  - `observation`
  - `action`
  - `reward`
  - `done`
  - `info`
- `episode_dataset.py` normalizes runtime `episodes.jsonl` into:
  - `train.jsonl`
  - `eval.jsonl`
  - `dataset_summary.json`
- filtering supports:
  - repairable only
  - unrecoverable only
  - all

The observation view intentionally captures both failure state and repair
context:

- failed request
- error code
- error message
- contract or schema summary
- candidate routes if present
- scenario type
- retry count

The action view intentionally captures the high-level repair decision:

- repair type
- selected endpoint
- method rewrite flag
- payload rewrite flag
- auth rewrite flag
- safe abstain flag

## Evaluation Outputs

The comparison layer now reports:

- `success_rate`
- `avg_reward`
- `avg_retries`
- `repairable_success_rate`
- `unrecoverable_safety_rate`
- `safe_abstention_accuracy`

When a learned policy has not been run yet, the comparison output records a
clear placeholder status instead of pretending a trained result exists.

## Optional Training Path

The repo now ships an optional TRL-style training scaffold:

- `sprint4.training.trl_train_grpo`
- `sprint4.evaluation.reward_curve`

This path is intentionally optional:

- benchmark and evaluation do not depend on TRL
- normal tests do not require TRL
- reward-curve plotting requires `matplotlib` from `requirements/training.txt`

If those extras are not installed, the benchmark, dataset, and comparison flows
remain fully usable.

## Backend Selection
Set either `REMORPH_S4_ENV_MODE` or `REMORPH_S4_ENV_BACKEND`.

Modes:

- `local`
- `live`

Backends:

- `simulated`
- `live`
- `openenv`

For live mode:

- `REMORPH_S4_LIVE_BASE_URL` (example: `http://127.0.0.1:8000`)
- live failures are normalized into the same workflow result format as local mode
- `422` responses are treated as payload/schema drift
- rich raw scenario names are mapped into `payload_drift`, `route_drift`, or `auth_drift`
- reports also retain `raw_scenario_type` so schema variants are not lost
- benchmark CLI supports:
  - representative live scenarios
  - all live scenarios from `target_api/training_dataset.json`
  - one filtered raw scenario
- representative auth prefers `auth_missing_tenant` because it is repairable via
  required header synthesis from contract evidence

For OpenEnv mode:

- `REMORPH_S4_OPENENV_CLIENT_MODULE` (example: `echo_env`)
- `REMORPH_S4_OPENENV_CLIENT_CLASS` (example: `EchoEnv`)
- `REMORPH_S4_OPENENV_BASE_URL`
- `REMORPH_S4_OPENENV_STRICT` (`true` to fail-fast on OpenEnv client errors)

## Current Evidence State

The cleanest current artifact bundle is:

- `runtime/sprint4_final_clean/package/`

That package demonstrates both:

- repairable drift, where adaptive repair beats baseline
- unrecoverable auth, where adaptive safely abstains instead of hallucinating
  credentials

One caveat is documented in the package itself: the unrecoverable-auth slice was
generated with the simulated backend in this environment because live socket
binding was blocked. That constraint does not invalidate the reward, abstention,
dataset, or comparison workflow.
