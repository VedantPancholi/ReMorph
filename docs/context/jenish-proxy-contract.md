# Jenish Proxy Contract

This file describes what ReMorph currently requires from Jenish's proxy and the
response format ReMorph already provides back.

## Contract Summary

Jenish should treat ReMorph as a repair module with one stable job:

1. accept a trapped upstream failure
2. return a structured repair or an explicit unrepairable state

The frozen repair boundary is `process_trapped_error()`. The proxy-facing
wrappers exist to make orchestration and failure handling easier.

## What ReMorph Requires From Jenish

Jenish's proxy should send a trapped failure payload shaped like `TrappedError`.

Minimum required fields:

```json
{
  "target_url": "https://mock.example.com/users",
  "method": "POST",
  "failed_payload": {
    "first_name": "John",
    "last_name": "Doe"
  },
  "failed_headers": {
    "Authorization": "Bearer demo-token"
  },
  "error_code": 400,
  "error_message": "Invalid request body"
}
```

Recommended integration fields:

```json
{
  "request_id": "req-123",
  "source_component": "proxy",
  "retry_count": 1
}
```

Integration guidance:

- always send the failing `target_url` and `method`
- preserve the exact broken headers and payload when possible
- attach `request_id` so telemetry and retries can be stitched together
- increment `retry_count` when the proxy re-enters ReMorph after another failed attempt

## Direct Python Adapter

Jenish can call:

- `app.main.process_trapped_error()`
- `app.main.process_trapped_error_safe()`
- `app.services.proxy_adapter.handle_proxy_failure()`
- `app.services.proxy_adapter.handle_proxy_failure_with_retry()`

`process_trapped_error()` is the frozen Sprint 2 repair contract.

## Preferred Usage

- use `process_trapped_error()` if the proxy only needs a repair object
- use `handle_proxy_failure()` if the proxy wants a JSON-safe contract envelope
- use `handle_proxy_failure_with_retry()` if the proxy wants ReMorph to manage one repair-and-retry workflow through a callback

## Response Envelope

`handle_proxy_failure()` returns:

```json
{
  "contract_version": "remorph.proxy.v1",
  "status": "healed",
  "healed_request": {
    "fixed_url": "https://mock.example.com/users",
    "fixed_method": "POST",
    "fixed_payload": {
      "user": {
        "f_name": "John",
        "l_name": "Doe"
      }
    },
    "fixed_headers": {
      "Authorization": "Bearer demo-token"
    },
    "healing_action": "payload_rewrite",
    "diagnostics": {
      "original_error_code": 400,
      "selected_endpoint_path": "/users",
      "docs_source": "local:app/testsupport/sample_openapi.json",
      "repair_strategy": "deterministic",
      "llm_attempted": true,
      "llm_succeeded": false,
      "fallback_used": true,
      "processing_ms": 120,
      "request_id": "req-123",
      "source_component": "proxy",
      "retry_count": 1
    }
  }
}
```

Fields to rely on:

- `contract_version`: current proxy envelope version
- `status`: `healed` or `unrepairable`
- `healed_request`: structured repair when available
- `failure_reason`: explicit reason when repair is not safe
- `message`: human-readable summary for logs or dashboards

## Retry Loop Adapter

If Jenish wants ReMorph to repair and then retry through a callback, use
`handle_proxy_failure_with_retry()`.

The executor callback receives:

```json
{
  "url": "https://mock.example.com/api/v2/finance/ledger",
  "method": "GET",
  "payload": null,
  "headers": {
    "x-api-key": "demo-token"
  },
  "request_id": "req-456",
  "attempt_number": 1
}
```

The executor should return:

```json
{
  "success": true,
  "status_code": 200,
  "response_body": {
    "ok": true
  },
  "error_message": null
}
```

Useful callback notes:

- `attempt_number` is the retry attempt for the repaired request
- `request_id` should flow through unchanged for traceability
- the callback should return the real upstream result, not a transformed proxy response

## Current Guarantee

Right now ReMorph provides:

- stable repair output format
- diagnostics for reward logging and debugging
- deterministic fallback if LLM repair fails
- cache reuse for repeated drift patterns

This is the current integration boundary Jenish can build against.

## Explicit Failure Format

If ReMorph cannot safely repair the request, it returns:

```json
{
  "contract_version": "remorph.proxy.v1",
  "status": "unrepairable",
  "healed_request": null,
  "failure_reason": "docs_unavailable",
  "message": "ReMorph could not safely generate a repair."
}
```

Current failure reasons:

- `docs_unavailable`
- `ambiguous_route_match`
- `schema_incomplete`
- `unsupported_auth_scheme`
- `no_repair_candidate`
- `unknown`

## What Jenish Does Not Need To Solve Inside Sprint 2

These concerns belong outside the frozen repair engine:

- transport retries outside the provided callback flow
- proxy authentication to external services
- environment mutation logic
- reward calculation
