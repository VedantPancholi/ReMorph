# Sachin Training Handoff

This file describes what Sachin can consume from ReMorph for Sprint 4 training,
reward logging, and evaluation.

## What Sachin Needs From ReMorph

ReMorph now produces:

- repaired request output
- diagnostics for each heal
- telemetry events on disk
- workflow-level retry results

Useful runtime artifacts:

- `runtime/telemetry/healing_events.jsonl`
- `runtime/telemetry/healing_summary.json`
- `runtime/telemetry/workflow_events.jsonl`
- `runtime/telemetry/workflow_summary.json`

## What To Use For Rewards

Suggested reward features:

- `diagnostics.original_error_code`
- `diagnostics.processing_ms`
- `diagnostics.docs_confidence`
- `diagnostics.spec_hash`
- `diagnostics.spec_version`
- `diagnostics.fallback_used`
- `healing_action`
- workflow `status`
- workflow `attempts`

Suggested reward sketch:

- `+1.0` if workflow status is `success`
- `+0.2` if attempts is `1`
- `-0.1` for each extra attempt
- `-0.2` if fallback was required
- `-0.2` if repair action was `no_change` after a real failure

## Complex Example

### Situation

Initial request:

```json
{
  "target_url": "https://mock.example.com/api/v1/transactions",
  "method": "GET",
  "failed_headers": {
    "Authorization": "Bearer demo-token"
  },
  "error_code": 404,
  "error_message": "Route not found",
  "request_id": "req-scenario-b",
  "source_component": "proxy",
  "retry_count": 1
}
```

ReMorph output:

```json
{
  "fixed_url": "https://mock.example.com/api/v2/finance/ledger",
  "fixed_method": "GET",
  "fixed_headers": {
    "x-api-key": "demo-token"
  },
  "healing_action": "combined_rewrite",
  "diagnostics": {
    "original_error_code": 404,
    "selected_endpoint_path": "/api/v2/finance/ledger",
    "docs_source": "local:app/testsupport/sample_openapi.json",
    "repair_strategy": "deterministic",
    "llm_attempted": true,
    "llm_succeeded": false,
    "fallback_used": true,
    "processing_ms": 145,
    "request_id": "req-scenario-b",
    "source_component": "proxy",
    "retry_count": 1
  }
}
```

Executor result:

```json
{
  "success": true,
  "status_code": 200,
  "response_body": {
    "ledger_entries": []
  }
}
```

### Why This Is Useful For Training

Sachin can now label this episode as:

- route drift + auth drift
- repaired in 1 attempt
- fallback path used
- final success achieved

That means you can compute:

- success rate by drift type
- average attempts to success
- fallback frequency
- processing time distribution

## What Sachin Still Needs To Build

- reward function implementation
- training script in Unsloth or HF TRL
- before/after evaluation harness
- reward curves and demo charts

ReMorph now provides the structured repair signals those pieces can consume.
