# Sachin Training Handoff

This file describes what Sachin can consume from ReMorph for Sprint 4 training,
reward logging, and evaluation.

## Handoff Summary

Sprint 2 is now stable enough to act as the repair component inside a larger
training loop. ReMorph does not train the policy by itself. It emits the repair
signals, telemetry, and workflow outputs that Sprint 4 can score.

## What Sachin Can Consume

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

## Suggested Reward Features

The most useful fields to consume are:

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

## What These Signals Let You Measure

From the current artifacts, Sachin can already compute:

- success rate by drift type
- average attempts to recovery
- deterministic fallback frequency
- docs-confidence distribution
- processing-latency distribution
- route-vs-payload-vs-auth repair mix

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

That means Sprint 4 can compute:

- success rate by drift type
- average attempts to success
- fallback frequency
- processing time distribution

It also gives you a clean training story:

- the original request failed
- ReMorph selected a new endpoint and auth scheme
- the retried request succeeded
- the reward can favor fast, correct recovery

## What Sachin Still Needs To Build

- reward function implementation
- training script in Unsloth or HF TRL
- before/after evaluation harness
- reward curves and demo charts

ReMorph now provides the structured repair signals those pieces can consume.

## Recommended Sprint 4 Inputs

When Sachin starts the training side, the most useful integration bundle is:

- trapped error payload
- healed request
- workflow result
- telemetry event stream
- spec metadata and docs confidence

That is enough to build a first reward pipeline without changing Sprint 2.
