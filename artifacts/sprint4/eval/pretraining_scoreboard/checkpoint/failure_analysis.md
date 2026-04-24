# Sprint 4 Failure Analysis

- Manifest id: `c6cc003f9220869e`

## Strongest Scenarios

- `auth_missing_tenant` adaptive success `1.0` (delta `1.0`)
- `route_invalid_path` adaptive success `1.0` (delta `1.0`)
- `route_method_spoof` adaptive success `1.0` (delta `1.0`)

## Weakest Scenarios

- `auth_malformed_jwt` adaptive success `1.0` (delta `0.0`)
- `auth_missing_token` adaptive success `1.0` (delta `0.0`)
- `schema_extra_key` adaptive success `1.0` (delta `0.0`)

## Training Focus

- Priority scenarios: `safety_calibration, retry_efficiency`
- Recommended focus: `retry_efficiency`
