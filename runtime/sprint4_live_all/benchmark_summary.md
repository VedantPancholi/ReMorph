# Sprint 4 Benchmark Summary

## Baseline
- Success rate: 16.28%
- Avg retries: 0.00
- Avg latency (ms): 43.44
- Avg reward: -0.674

## Adaptive ReMorph
- Success rate: 39.53%
- Avg retries: 0.81
- Avg latency (ms): 322.44
- Avg reward: -0.156

## Delta (Adaptive - Baseline)
- Success rate delta: 0.233
- Avg retries delta: 0.814
- Avg latency delta (ms): 279.000
- Reward delta: 0.519

## Per Scenario Accuracy (Adaptive)
- payload_drift: 58.33%
- route_drift: 33.33%
- auth_drift: 31.25%

## Per Raw Scenario Accuracy (Adaptive)
- schema_missing_key: 33.33%
- schema_type_coercion: 33.33%
- schema_extra_key: 100.00%
- schema_null_injection: 66.67%
- route_regression: 60.00%
- route_method_spoof: 0.00%
- route_invalid_path: 40.00%
- auth_missing_token: 0.00%
- auth_malformed_jwt: 0.00%
- auth_missing_tenant: 80.00%
- success_attempt: 100.00%
