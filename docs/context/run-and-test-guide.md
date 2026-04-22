# Run And Test Guide

This guide explains how to run ReMorph locally, how to execute the three demo
scenarios, and how to decide whether the output is correct.

Important:

- Prefer `.venv/bin/python` and `.venv/bin/pytest` so you use the project
  dependencies, not system Python.
- If you activate the environment first with `source .venv/bin/activate`, then
  `python ...` and `pytest ...` are also fine.

## 1. Setup

Create a virtual environment:

```bash
python3 -m venv .venv
```

Install dependencies:

```bash
.venv/bin/pip install -r requirements.txt
```

Optional activation:

```bash
source .venv/bin/activate
```

Create your local environment file:

```bash
cp .env.example .env
```

If you want model-assisted healing, add your Groq key to `.env`:

```env
REMORPH_GROQ_API_KEY=your_key_here
```

Important:

- ReMorph can run the demo scenarios even without the key because deterministic
  repair is already implemented.
- If the key is present, the model becomes an optional refinement layer.
- Keep the key in `.env` only. Do not paste it into `app/config.py` or any
  tracked file.

## 2. What Each Run Mode Means

### Smoke Mode

Smoke mode does not call the healing model. It only checks that:

- the trapped error is valid
- the local OpenAPI spec can be loaded
- the correct route is found
- the schema and auth requirements are extracted correctly

Run it like this:

```bash
.venv/bin/python run_local_test.py --mode smoke --scenario a
.venv/bin/python run_local_test.py --mode smoke --scenario b
.venv/bin/python run_local_test.py --mode smoke --scenario c
```

### Heal Mode

Heal mode runs the full pipeline:

1. validate trapped error
2. load spec
3. extract endpoint schema
4. build repair context
5. produce healed request

Run it like this:

```bash
.venv/bin/python run_local_test.py --mode heal --scenario a
.venv/bin/python run_local_test.py --mode heal --scenario b
.venv/bin/python run_local_test.py --mode heal --scenario c
```

### Direct Application Entry

The real integration entry point for proxy/Sprint 4 work is:

- `app.main.process_trapped_error()`
- `app.services.proxy_adapter.handle_proxy_failure()`
- `app.services.proxy_adapter.handle_proxy_failure_with_retry()`

It accepts a trapped error dictionary and returns a JSON-safe healed response.
`run_local_test.py` is only a convenience wrapper around that core entry point.

### Retry Loop Adapter

If you want to simulate Jenish's proxy flow locally, use the retry orchestrator
through `handle_proxy_failure_with_retry()` or `heal_and_retry()`. These APIs
let you inject a fake executor callback and observe:

- repaired request
- retry count
- final success/failure
- workflow telemetry

## 3. What Correct Output Looks Like

The output is correct when the repaired request matches the changed API
contract, not the old broken request.

### Scenario A: Payload Drift

Command:

```bash
.venv/bin/python run_local_test.py --mode heal --scenario a
```

Input problem:

- old payload uses `first_name` and `last_name`
- new schema expects nested `user.f_name` and `user.l_name`

Correct output should include:

- `healing_action` = `payload_rewrite`
- `fixed_url` still points to `/users`
- `diagnostics.selected_endpoint_path` = `/users`
- `fixed_payload` becomes:

```json
{
  "user": {
    "f_name": "John",
    "l_name": "Doe"
  }
}
```

Why this is correct:

- the payload now matches the schema in `sample_openapi.json`
- the old flat shape is no longer used

### Scenario B: Route Drift

Command:

```bash
.venv/bin/python run_local_test.py --mode heal --scenario b
```

Input problem:

- old route is `/api/v1/transactions`
- new route is `/api/v2/finance/ledger`
- the new endpoint also requires `x-api-key`

Correct output should include:

- `fixed_url` = `https://mock.example.com/api/v2/finance/ledger`
- `healing_action` = `combined_rewrite`
- `diagnostics.selected_endpoint_path` = `/api/v2/finance/ledger`
- `fixed_headers` contains:

```json
{
  "x-api-key": "demo-token"
}
```

Why this is correct:

- the request is moved to the new endpoint
- the auth scheme now matches the new route requirements

### Scenario C: Auth Drift

Command:

```bash
.venv/bin/python run_local_test.py --mode heal --scenario c
```

Input problem:

- old header uses `Authorization: Bearer demo-token`
- new endpoint expects `x-api-key: demo-token`

Correct output should include:

- `healing_action` = `auth_rewrite`
- `fixed_url` remains `/api/v2/finance/ledger`
- `diagnostics.selected_endpoint_path` = `/api/v2/finance/ledger`
- `fixed_headers` becomes:

```json
{
  "x-api-key": "demo-token"
}
```

Why this is correct:

- the token is preserved
- only the auth format changes

## 4. Fast Correctness Checklist

Whenever you run `--mode heal`, validate these five things:

1. `fixed_url` matches the updated route from the spec.
2. `fixed_payload` uses only fields that exist in the schema.
3. `fixed_headers` match the documented auth scheme.
4. `healing_action` matches what changed.
5. `schema_summary` reflects the endpoint that was actually selected.

If these five are true, the output is behaving correctly for Sprint 2.

Also validate the new diagnostics block:

1. `diagnostics.docs_source` shows which spec source was used.
2. `diagnostics.selected_endpoint_path` matches the chosen endpoint.
3. `diagnostics.repair_strategy` tells you whether the result came from deterministic, merged, or LLM-assisted behavior.
4. `diagnostics.fallback_used` tells you whether model refinement failed and deterministic repair was used instead.
5. `diagnostics.request_id` and `diagnostics.retry_count` preserve proxy-side context for Sprint 4.
6. `diagnostics.docs_confidence`, `diagnostics.spec_hash`, and `diagnostics.spec_version` help explain how reliable the chosen repair context was.

## 5. Automated Tests

Run the test suite:

```bash
.venv/bin/pytest -q
```

If you activated the venv already, this also works:

```bash
pytest -q
```

Current coverage checks:

- local OpenAPI loading
- route extraction
- parameterized route matching
- nested payload schema extraction
- prompt construction
- healing response parsing
- deterministic fallback repair for payload drift
- deterministic fallback repair for route drift
- deterministic fallback repair for auth drift
- proxy adapter contract
- repair cache read/write
- retry orchestration success path
- explicit unrepairable proxy failure response
- local spec metadata output

If tests pass, the current repo baseline is internally consistent.

## 6. How To Test With The Groq Key

After adding `REMORPH_GROQ_API_KEY` to `.env`, run:

```bash
.venv/bin/python run_local_test.py --mode heal --scenario a
```

What changes when the key is present:

- the deterministic repair still prepares a safe baseline
- the LLM may return a refined healed response
- if the model fails, ReMorph still falls back to the deterministic repair
- if the LLM returns malformed text instead of valid JSON, ReMorph now treats
  that as a model failure and still falls back safely

For the strongest Groq-side structured output support, prefer a model that
supports Structured Outputs such as `openai/gpt-oss-20b` or
`openai/gpt-oss-120b`. Other models fall back to JSON object mode.

How to judge model-assisted correctness:

- it must not invent fields outside the schema
- it must not keep the old broken route or auth shape
- it should remain at least as correct as the deterministic output

## 7. Demo Flow Recommendation

For a live demo:

1. Run `scenario a` in smoke mode to show schema discovery.
2. Run `scenario a` in heal mode to show repaired payload.
3. Run `scenario b` in heal mode to show route shift handling.
4. Run `scenario c` in heal mode to show auth drift handling.
5. Run `pytest -q` to show the project has repeatable checks, not just manual output.

## 8. Files Involved In Validation

- `run_local_test.py`: local runner
- `app/main.py`: integration-ready entry point
- `app/services/proxy_adapter.py`: Jenish-facing contract
- `app/services/retry_orchestrator.py`: repair-and-retry orchestration
- `app/services/telemetry.py`: persistent event sink
- `app/services/repair_cache.py`: repeated-drift cache
- `app/testsupport/sample_errors.py`: trapped error inputs
- `app/testsupport/sample_openapi.json`: changed API contract
- `tests/test_healer.py`: correctness checks for fallback repair
- `tests/test_schema_extractor.py`: route and schema extraction checks
