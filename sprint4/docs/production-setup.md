# Production Setup

## 1) Base Install
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-sprint4.txt
```

## 2) Configure
Copy `.env.example` to `.env` and set Sprint 4 values:

- `REMORPH_S4_ENV_BACKEND=simulated` for local CI-style runs
- `REMORPH_S4_ENV_BACKEND=openenv` for OpenEnv-backed runs
- OpenEnv client module/class/base URL when using OpenEnv

## 3) Run Demo
```bash
python scripts/run_sprint4_demo.py
```

## 4) Run Benchmark
```bash
python scripts/run_benchmark.py --episodes-per-scenario 5
```

## 5) Export Summary
```bash
python scripts/export_metrics.py
```

## Engineering Practices (Recommended)
- Use `simulated` backend in tests and CI for deterministic checks.
- Use `openenv` backend in staging/prod-like eval jobs.
- Version your drift contracts and benchmark reports.
- Fail fast in production with `REMORPH_S4_OPENENV_STRICT=true`.
- Keep reward constants under code review; treat as policy config.

