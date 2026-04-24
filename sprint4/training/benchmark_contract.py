"""Frozen Sprint 4 benchmark contract for RL-ready scenario slices."""

from __future__ import annotations

from typing import Literal

BenchmarkPartition = Literal["repairable", "unrecoverable", "all"]
BENCHMARK_CONTRACT_VERSION = "v1"

REPAIRABLE_RAW_SCENARIOS: tuple[str, ...] = (
    "schema_missing_key",
    "schema_type_coercion",
    "schema_extra_key",
    "schema_null_injection",
    "route_regression",
    "route_method_spoof",
    "route_invalid_path",
    "auth_missing_tenant",
)

UNRECOVERABLE_RAW_SCENARIOS: tuple[str, ...] = (
    "auth_missing_token",
    "auth_malformed_jwt",
)


def raw_scenarios_for_partition(partition: BenchmarkPartition) -> tuple[str, ...]:
    """Return the frozen raw scenario slice for one benchmark partition."""

    if partition == "repairable":
        return REPAIRABLE_RAW_SCENARIOS
    if partition == "unrecoverable":
        return UNRECOVERABLE_RAW_SCENARIOS
    return REPAIRABLE_RAW_SCENARIOS + UNRECOVERABLE_RAW_SCENARIOS


def get_repairable_scenarios() -> tuple[str, ...]:
    """Return the repairable raw scenarios from the frozen contract."""

    return REPAIRABLE_RAW_SCENARIOS


def get_unrecoverable_scenarios() -> tuple[str, ...]:
    """Return the unrecoverable raw scenarios from the frozen contract."""

    return UNRECOVERABLE_RAW_SCENARIOS


def classify_raw_scenario(raw_scenario_type: str | None) -> BenchmarkPartition | None:
    """Classify one raw scenario into the frozen benchmark contract."""

    if raw_scenario_type in REPAIRABLE_RAW_SCENARIOS:
        return "repairable"
    if raw_scenario_type in UNRECOVERABLE_RAW_SCENARIOS:
        return "unrecoverable"
    return None


def is_repairable_raw_scenario(raw_scenario_type: str | None) -> bool:
    """Return True when the raw scenario belongs to the repairable RL slice."""

    return raw_scenario_type in REPAIRABLE_RAW_SCENARIOS


def is_unrecoverable_raw_scenario(raw_scenario_type: str | None) -> bool:
    """Return True when the raw scenario belongs to the unrecoverable RL slice."""

    return raw_scenario_type in UNRECOVERABLE_RAW_SCENARIOS


def is_repairable(raw_scenario_type: str | None) -> bool:
    """Alias for repairable classification used by Phase 2 code."""

    return is_repairable_raw_scenario(raw_scenario_type)


def is_unrecoverable(raw_scenario_type: str | None) -> bool:
    """Alias for unrecoverable classification used by Phase 2 code."""

    return is_unrecoverable_raw_scenario(raw_scenario_type)
