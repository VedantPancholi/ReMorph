# Jenish Proxy Contract

This file describes what ReMorph currently requires from Jenish's proxy and the
response format ReMorph already provides back.

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

## Direct Python Adapter

Jenish can call:

- `app.services.proxy_adapter.handle_proxy_failure()`
- `app.services.proxy_adapter.handle_proxy_failure_with_retry()`

## Current Response Format

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

## Current Guarantee

Right now ReMorph provides:

- stable repair output format
- diagnostics for reward logging and debugging
- deterministic fallback if LLM repair fails
- cache reuse for repeated drift patterns

This is the current integration boundary Jenish can build against.
