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
- `sprint4/env/`: backend interface, simulated mutable API env, OpenEnv adapter, drift modes
- `sprint4/proxy/`: execution, trap/repair handoff, retry workflow, episode logging
- `sprint4/rewards/`: deterministic reward scoring
- `sprint4/evaluation/`: benchmark + report generation
- `sprint4/training/`: optional GRPO scaffold scripts

## Integration Contract
- Sprint 2 remains unchanged.
- Sprint 4 only calls:
  - `app.main.process_trapped_error()`
- Sprint 4 passes drift-specific contract path via `local_spec_path`.

## Environment Backends
- `simulated` (default): deterministic in-memory env for local development and CI.
- `openenv`: production-facing adapter that uses OpenEnv client `reset()`, `step()`, and `state()` APIs.

## Backend Selection
Set `REMORPH_S4_ENV_BACKEND`:

- `simulated`
- `openenv`

For OpenEnv mode:

- `REMORPH_S4_OPENENV_CLIENT_MODULE` (example: `echo_env`)
- `REMORPH_S4_OPENENV_CLIENT_CLASS` (example: `EchoEnv`)
- `REMORPH_S4_OPENENV_BASE_URL`
- `REMORPH_S4_OPENENV_STRICT` (`true` to fail-fast on OpenEnv client errors)
