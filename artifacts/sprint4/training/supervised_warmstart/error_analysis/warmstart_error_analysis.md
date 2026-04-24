# Warm-Start Error Analysis

- Manifest id: `c6cc003f9220869e`
- Row count: `10`

## Missed By Scenario

- `auth_missing_tenant` missed `1` of `1`
- `route_method_spoof` missed `1` of `1`
- `route_regression` missed `1` of `1`
- `schema_missing_key` missed `1` of `1`
- `schema_type_coercion` missed `1` of `1`

## Action Confusion

- `abstain` -> abstain=2
- `no_op` -> no_op=1
- `repair_auth` -> repair_payload=1
- `repair_payload` -> repair_payload=4
- `repair_route` -> repair_route=2

## Largest Reward Gaps

- `route_regression` predicted `repair_route` vs target `repair_route`, reward gap `22.0`
- `schema_type_coercion` predicted `repair_payload` vs target `repair_payload`, reward gap `20.0`
- `schema_missing_key` predicted `repair_payload` vs target `repair_payload`, reward gap `20.0`
- `auth_missing_tenant` predicted `repair_payload` vs target `repair_auth`, reward gap `20.0`
- `route_method_spoof` predicted `repair_payload` vs target `repair_payload`, reward gap `18.0`