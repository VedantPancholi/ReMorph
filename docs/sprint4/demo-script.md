# Sprint 4 Demo Script

## Live Flow
1. Run one baseline episode against drifted contract.
2. Show failure (typically 400/401/404).
3. Run one adaptive episode.
4. Show trapped error, repair decision, retry, and reward.

## Command
```bash
python scripts/run_sprint4_demo.py
```

## Run with OpenEnv
```bash
set REMORPH_S4_ENV_BACKEND=openenv
set REMORPH_S4_OPENENV_CLIENT_MODULE=echo_env
set REMORPH_S4_OPENENV_CLIENT_CLASS=EchoEnv
set REMORPH_S4_OPENENV_BASE_URL=https://openenv-echo-env.hf.space
python scripts/run_sprint4_demo.py
```

## What To Highlight
- Drift type and contract mutation
- Original request vs healed request
- Retry outcome
- Baseline vs adaptive reward difference
