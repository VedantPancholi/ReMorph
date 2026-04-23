# Run And Test Guide

This guide is the main runbook for ReMorph. It covers setup, local demo flows,
test execution, correctness checks, and the expected behavior of the Sprint 2
repair engine.

Important:

- prefer `.venv/bin/python` and `.venv/bin/pytest` so you use the project dependencies
- if you activate the environment with `source .venv/bin/activate`, plain `python` and `pytest` are fine too
- deterministic repair works without a provider key, so local validation does not depend on Groq

## 1. Setup

Create the environment and install dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Optional activation:

```bash
source .venv/bin/activate
```

If you want model-assisted refinement, add this to `.env`:

```env
REMORPH_GROQ_API_KEY=your_key_here
```

Security note:

- keep the key in `.env` only
- never paste secrets into tracked Python files or Markdown docs

## 1A. Docker Setup

If you want anyone to run ReMorph without creating a local Python environment,
use Docker.

Build the image:

```bash
docker build -t remorph .
```

Default container run:

```bash
docker run --rm remorph
```

That default command maps to:

```bash
python run_local_test.py --mode smoke --scenario a
```

Run a full healing scenario:

```bash
docker run --rm remorph --mode heal --scenario a
docker run --rm remorph --mode heal --scenario b
docker run --rm remorph --mode heal --scenario c
```

Pass local environment variables into the container:

```bash
docker run --rm --env-file .env remorph --mode heal --scenario a
```

Persist runtime artifacts like cache and telemetry on the host:

```bash
docker run --rm --env-file .env -v "$(pwd)/runtime:/app/runtime" remorph --mode heal --scenario a
```

Run tests inside Docker:

```bash
docker run --rm --entrypoint pytest remorph -q
```

## 2. Fastest Way To Run Everything

Use this sequence from the repo root:

```bash
.venv/bin/pytest -q
.venv/bin/python run_local_test.py --mode smoke --scenario a
.venv/bin/python run_local_test.py --mode smoke --scenario b
.venv/bin/python run_local_test.py --mode smoke --scenario c
.venv/bin/python run_local_test.py --mode heal --scenario a
.venv/bin/python run_local_test.py --mode heal --scenario b
.venv/bin/python run_local_test.py --mode heal --scenario c
```

This gives you:

- automated validation
- schema-extraction validation
- full repair validation for payload, route, and auth drift

Docker equivalent:

```bash
docker run --rm --entrypoint pytest remorph -q
docker run --rm remorph --mode smoke --scenario a
docker run --rm remorph --mode smoke --scenario b
docker run --rm remorph --mode smoke --scenario c
docker run --rm --env-file .env remorph --mode heal --scenario a
docker run --rm --env-file .env remorph --mode heal --scenario b
docker run --rm --env-file .env remorph --mode heal --scenario c
```

## 3. What Each Run Mode Means

### Smoke Mode

Smoke mode does not call the healing model. It verifies that ReMorph can:

- validate the trapped error
- load the spec
- find the correct route
- extract schema and auth requirements

Commands:

```bash
.venv/bin/python run_local_test.py --mode smoke --scenario a
.venv/bin/python run_local_test.py --mode smoke --scenario b
.venv/bin/python run_local_test.py --mode smoke --scenario c
```

### Heal Mode

Heal mode runs the real Sprint 2 repair flow:

1. validate trapped error
2. load docs/spec metadata
3. extract the best endpoint contract
4. prepare deterministic repair
5. optionally ask the model for refinement
6. return a `HealedRequest` with diagnostics

Commands:

```bash
.venv/bin/python run_local_test.py --mode heal --scenario a
.venv/bin/python run_local_test.py --mode heal --scenario b
.venv/bin/python run_local_test.py --mode heal --scenario c
```

## 4. Integration Entry Points

The stable callable boundary for Sprint 2 is:

- `app.main.process_trapped_error()`

Safe orchestration wrappers:

- `app.main.process_trapped_error_safe()`
- `app.services.proxy_adapter.handle_proxy_failure()`
- `app.services.proxy_adapter.handle_proxy_failure_with_retry()`

`run_local_test.py` is only a local harness around these core interfaces.

## 5. Scenario Expectations

The output is correct when the repaired request matches the changed contract,
not when it preserves the original broken request.

### Scenario A: Payload Drift

Command:

```bash
.venv/bin/python run_local_test.py --mode heal --scenario a
```

Expected behavior:

- `healing_action` is `payload_rewrite`
- `fixed_url` remains `/users`
- `diagnostics.selected_endpoint_path` is `/users`
- `fixed_payload` becomes:

```json
{
  "user": {
    "f_name": "John",
    "l_name": "Doe"
  }
}
```

### Scenario B: Route Drift

Command:

```bash
.venv/bin/python run_local_test.py --mode heal --scenario b
```

Expected behavior:

- `healing_action` is `combined_rewrite`
- `fixed_url` becomes `https://mock.example.com/api/v2/finance/ledger`
- `diagnostics.selected_endpoint_path` is `/api/v2/finance/ledger`
- `fixed_headers` contains:

```json
{
  "x-api-key": "demo-token"
}
```

### Scenario C: Auth Drift

Command:

```bash
.venv/bin/python run_local_test.py --mode heal --scenario c
```

Expected behavior:

- `healing_action` is `auth_rewrite`
- `fixed_url` stays on `/api/v2/finance/ledger`
- `diagnostics.selected_endpoint_path` is `/api/v2/finance/ledger`
- `fixed_headers` becomes:

```json
{
  "x-api-key": "demo-token"
}
```

## 6. Correctness Checklist

Whenever you run `--mode heal`, validate these output fields:

1. `fixed_url` matches the updated route from the spec.
2. `fixed_payload` uses only fields present in the extracted schema.
3. `fixed_headers` match the documented auth requirement.
4. `healing_action` reflects what actually changed.
5. `schema_summary` or extracted schema context points to the selected endpoint.

Also validate diagnostics:

1. `diagnostics.docs_source` shows which spec source was used.
2. `diagnostics.selected_endpoint_path` matches the chosen endpoint.
3. `diagnostics.repair_strategy` tells you whether the result was deterministic, merged, or LLM-assisted.
4. `diagnostics.fallback_used` tells you whether the model path failed and deterministic repair was used instead.
5. `diagnostics.docs_confidence`, `diagnostics.spec_hash`, and `diagnostics.spec_version` explain the reliability of the contract that was chosen.
6. `diagnostics.request_id` and `diagnostics.retry_count` preserve proxy-side context for Sprint 4.

Also validate route-explainability signals:

1. `route_match_score` and `route_match_confidence` are present.
2. `ranked_candidate_endpoints` shows the top route options.
3. `route_match_reason` explains why the winning route was selected.

## 7. Automated Tests

Run the full suite:

```bash
.venv/bin/pytest -q
```

Targeted suites:

```bash
.venv/bin/pytest tests/test_schema_extractor.py tests/test_schema_matching.py -q
.venv/bin/pytest tests/test_healer.py -q
.venv/bin/pytest tests/test_retry_orchestrator.py -q
```

Docker equivalents:

```bash
docker run --rm --entrypoint pytest remorph tests/test_schema_extractor.py tests/test_schema_matching.py -q
docker run --rm --entrypoint pytest remorph tests/test_healer.py -q
docker run --rm --entrypoint pytest remorph tests/test_retry_orchestrator.py -q
```

Current coverage includes:

- local OpenAPI loading and spec metadata
- nested payload extraction
- parameterized route matching
- ambiguous match handling
- low-confidence route rejection
- ranked route recovery when exact matching fails
- deterministic payload, route, and auth repair
- model-output parsing and fallback behavior
- proxy adapter contract
- retry orchestration
- repair cache behavior

If these tests pass, the current Sprint 2 baseline is internally consistent.

## 8. Model-Assisted Validation

After adding `REMORPH_GROQ_API_KEY` to `.env`, run:

```bash
.venv/bin/python run_local_test.py --mode heal --scenario a
```

What changes when the key is present:

- deterministic repair still prepares a safe baseline
- the model may refine the repaired output
- if the model fails or returns invalid structure, ReMorph falls back safely

Model-assisted correctness still has to obey the same contract:

- no invented fields outside the schema
- no preservation of the old broken route or auth shape
- no downgrade from the deterministic baseline

## 9. Runtime Artifacts To Inspect

After running heal flows, inspect:

- `runtime/repair_cache.json`
- `runtime/telemetry/healing_events.jsonl`
- `runtime/telemetry/healing_summary.json`
- `runtime/telemetry/workflow_events.jsonl`
- `runtime/telemetry/workflow_summary.json`

These files are especially useful for team handoff, reward design, and demo screenshots.

## 10. Demo Flow

For a live walkthrough:

1. run `scenario a` in smoke mode to show schema discovery
2. run `scenario a` in heal mode to show payload correction
3. run `scenario b` in heal mode to show route plus auth correction
4. run `scenario c` in heal mode to show auth-only correction
5. run `pytest -q` to show the behavior is repeatable

## 11. Troubleshooting

If `python run_local_test.py ...` fails but `.venv/bin/python run_local_test.py ...` works:

- you are using system Python instead of the project environment

If `docker run ... --env-file .env ...` does not see your key:

- confirm `.env` exists in the repo root
- confirm the variable name is `REMORPH_GROQ_API_KEY`

If runtime files are missing after a Docker run:

- mount the runtime directory with `-v "$(pwd)/runtime:/app/runtime"`
- remember that container-local files disappear when `--rm` is used without a bind mount

If tests become nondeterministic:

- confirm that test files isolate local secrets such as `REMORPH_GROQ_API_KEY`

If a heal run falls back to deterministic repair:

- that is acceptable behavior
- check `diagnostics.fallback_used`, `diagnostics.llm_attempted`, and `diagnostics.llm_succeeded`

If route matching fails:

- inspect `route_match_confidence`, `route_match_reason`, and `ranked_candidate_endpoints`
- compare against `app/testsupport/sample_openapi.json`

## 12. Sprint 4 Run Flow

Sprint 4 adds a mutable environment, retry loop, reward scoring, and benchmark
artifacts around the frozen Sprint 2 repair brain. The default local backend is
the deterministic `simulated` env, which is the fastest way to validate the
full loop before switching to OpenEnv.

Fastest Sprint 4 verification from the repo root:

```bash
.venv/bin/pytest -q tests/test_sprint4_reward_function.py tests/test_sprint4_env_factory.py tests/test_sprint4_openenv_adapter.py tests/test_sprint4_env_mutation.py tests/test_sprint4_workflow_runner.py tests/test_sprint4_benchmark_runner.py
.venv/bin/python scripts/run_sprint4_demo.py
.venv/bin/python scripts/run_benchmark.py --episodes-per-scenario 1
```

What those commands prove:

- the simulated env returns the expected `400`, `404`, and `401` drift failures
- the adaptive flow traps the failure, calls `process_trapped_error()`, retries, and succeeds
- the demo script prints one baseline-vs-adaptive episode
- the benchmark writes `episodes.jsonl`, `benchmark_report.json`, and `benchmark_summary.md` under `runtime/sprint4/`

Expected Sprint 4 control flow:

1. load the contract bundle for baseline plus drift contracts
2. reset the environment and apply one drift mode
3. send the original request
4. capture the failing response
5. package the failure as `TrappedError`
6. run Sprint 2 repair against the active drift contract
7. retry the healed request
8. score the reward and persist one episode log

To switch later to OpenEnv instead of the local simulator:

```bash
export REMORPH_S4_ENV_BACKEND=openenv
export REMORPH_S4_OPENENV_CLIENT_MODULE=your_openenv_module
export REMORPH_S4_OPENENV_CLIENT_CLASS=YourOpenEnvClient
.venv/bin/python scripts/run_sprint4_demo.py
```

That keeps the same Sprint 4 flow while swapping only the backend implementation.
