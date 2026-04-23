"""Load Sprint 4 contract fixtures and default benchmark scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.services.doc_fetcher import load_local_spec

DriftMode = Literal["payload", "route", "auth"]


@dataclass(frozen=True)
class ScenarioRequest:
    """One benchmark scenario for Sprint 4 episodes."""

    scenario_type: str
    drift_mode: DriftMode
    method: str
    url: str
    headers: dict[str, str] | None
    payload: dict[str, Any] | None


@dataclass(frozen=True)
class ContractBundle:
    """Loaded baseline and drifted contracts for the environment."""

    baseline_contract: dict[str, Any]
    drift_contracts: dict[DriftMode, dict[str, Any]]
    drift_paths: dict[DriftMode, str]


def load_contract_bundle() -> ContractBundle:
    """Load JSON fixtures used by the Sprint 4 environment."""
    baseline_path = "sprint4/env/contracts/baseline_openapi.json"
    drift_paths: dict[DriftMode, str] = {
        "payload": "sprint4/env/contracts/drift_payload.json",
        "route": "sprint4/env/contracts/drift_route.json",
        "auth": "sprint4/env/contracts/drift_auth.json",
    }
    return ContractBundle(
        baseline_contract=load_local_spec(baseline_path),
        drift_contracts={
            mode: load_local_spec(path)
            for mode, path in drift_paths.items()
        },
        drift_paths=drift_paths,
    )


def default_scenarios() -> list[ScenarioRequest]:
    """Return the three deterministic Sprint 4 benchmark scenarios."""
    return [
        ScenarioRequest(
            scenario_type="payload_drift",
            drift_mode="payload",
            method="POST",
            url="https://mock.example.com/users",
            headers={"Authorization": "Bearer demo-token"},
            payload={"first_name": "John", "last_name": "Doe"},
        ),
        ScenarioRequest(
            scenario_type="route_drift",
            drift_mode="route",
            method="GET",
            url="https://mock.example.com/api/v1/transactions",
            headers={"Authorization": "Bearer demo-token"},
            payload=None,
        ),
        ScenarioRequest(
            scenario_type="auth_drift",
            drift_mode="auth",
            method="GET",
            url="https://mock.example.com/api/v2/finance/ledger",
            headers={"Authorization": "Bearer demo-token"},
            payload=None,
        ),
    ]
