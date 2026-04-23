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
11. Evaluation compares baseline vs adaptive

## Modules
- `sprint4/env/`: backend interface, simulated mutable API env, live FastAPI adapter, OpenEnv adapter, drift modes, live failure parsing
- `sprint4/proxy/`: execution, trap/repair handoff, retry workflow, episode logging
- `sprint4/rewards/`: deterministic reward scoring
- `sprint4/evaluation/`: benchmark + report generation across local and live modes
- `sprint4/training/`: optional GRPO scaffold scripts plus Phase 1 dataset adapter

## Integration Contract
- Sprint 2 remains unchanged.
- Sprint 4 only calls:
  - `app.main.process_trapped_error()`
- Sprint 4 passes drift-specific contract path via `local_spec_path`.

## Environment Modes
- `local`: uses the `simulated` backend for deterministic in-memory drift tests.
- `live`: uses the Sprint 1 FastAPI target server over HTTP.

## Environment Backends
- `simulated` (default backend for `local` mode): deterministic in-memory env for local development and CI.
- `live`: HTTP adapter around the Sprint 1 FastAPI target server.
- `openenv`: production-facing adapter that uses OpenEnv client `reset()`, `step()`, and `state()` APIs.

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
  - all live scenarios from `training_dataset.json`
  - one filtered raw scenario
- representative auth prefers `auth_missing_tenant` because it is repairable via
  required header synthesis from contract evidence

For OpenEnv mode:

- `REMORPH_S4_OPENENV_CLIENT_MODULE` (example: `echo_env`)
- `REMORPH_S4_OPENENV_CLIENT_CLASS` (example: `EchoEnv`)
- `REMORPH_S4_OPENENV_BASE_URL`
- `REMORPH_S4_OPENENV_STRICT` (`true` to fail-fast on OpenEnv client errors)
