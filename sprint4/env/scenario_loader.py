"""Load Sprint 4 contract fixtures and default benchmark scenarios."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.services.doc_fetcher import load_local_spec
from sprint4.env.live_support import map_scenario_to_category

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
    local_spec_path: str | None = None
    raw_scenario_type: str | None = None


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
            raw_scenario_type="schema_missing_key",
            drift_mode="payload",
            method="POST",
            url="https://mock.example.com/users",
            headers={"Authorization": "Bearer demo-token"},
            payload={"first_name": "John", "last_name": "Doe"},
            local_spec_path=drift_paths()["payload"],
        ),
        ScenarioRequest(
            scenario_type="route_drift",
            raw_scenario_type="route_regression",
            drift_mode="route",
            method="GET",
            url="https://mock.example.com/api/v1/transactions",
            headers={"Authorization": "Bearer demo-token"},
            payload=None,
            local_spec_path=drift_paths()["route"],
        ),
        ScenarioRequest(
            scenario_type="auth_drift",
            raw_scenario_type="auth_missing_tenant",
            drift_mode="auth",
            method="GET",
            url="https://mock.example.com/api/v2/finance/ledger",
            headers={"Authorization": "Bearer demo-token"},
            payload=None,
            local_spec_path=drift_paths()["auth"],
        ),
    ]


def default_live_scenarios(
    dataset_path: str = "target_api/training_dataset.json",
    *,
    live_spec_path: str = "chaos_gym/specs/openapi.json",
    selection: str = "representative",
    raw_scenario_filter: str | None = None,
) -> list[ScenarioRequest]:
    """Return representative live requests seeded from the Phase 1 dataset."""

    file_path = Path(dataset_path)
    if file_path.exists():
        try:
            records = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            records = []
        if isinstance(records, list):
            selected = _select_live_scenarios(
                records,
                live_spec_path=live_spec_path,
                selection=selection,
                raw_scenario_filter=raw_scenario_filter,
            )
            if selected:
                return selected

    return [
        ScenarioRequest(
            scenario_type="payload_drift",
            raw_scenario_type="schema_missing_key",
            drift_mode="payload",
            method="POST",
            url="http://127.0.0.1:8000/api/v1/payments/process",
            headers={
                "x-api-key": "secret",
                "x-vendor-id": "ven-123",
                "Authorization": f"Bearer {_demo_jwt()}",
            },
            payload={
                "amount": 100,
                "card_details": {
                    "card_number": "1234567812345678",
                    "cvv": "123",
                    "expiry": "12/26",
                },
                "billing_address": {
                    "street": "123 Main St",
                    "zip_code": "12345",
                    "iso_country": "US",
                },
            },
            local_spec_path=live_spec_path,
        ),
        ScenarioRequest(
            scenario_type="route_drift",
            raw_scenario_type="route_regression",
            drift_mode="route",
            method="GET",
            url="http://127.0.0.1:8000/api/v0/ledger/transactions?start_date=2024-01-01T00:00:00Z&end_date=2024-01-31T00:00:00Z&limit=100",
            headers={"Authorization": f"Bearer {_demo_jwt()}"},
            payload=None,
            local_spec_path=live_spec_path,
        ),
    ]


def drift_paths() -> dict[DriftMode, str]:
    return {
        "payload": "sprint4/env/contracts/drift_payload.json",
        "route": "sprint4/env/contracts/drift_route.json",
        "auth": "sprint4/env/contracts/drift_auth.json",
    }


def _select_live_scenarios(
    records: list[dict[str, Any]],
    *,
    live_spec_path: str,
    selection: str,
    raw_scenario_filter: str | None,
) -> list[ScenarioRequest]:
    if raw_scenario_filter:
        selected = [
            item for item in _records_to_live_scenarios(records, live_spec_path=live_spec_path)
            if item.raw_scenario_type == raw_scenario_filter
        ]
        return selected
    if selection == "all":
        return _records_to_live_scenarios(records, live_spec_path=live_spec_path)
    return _pick_live_representatives(records, live_spec_path=live_spec_path)


def _pick_live_representatives(
    records: list[dict[str, Any]],
    *,
    live_spec_path: str,
) -> list[ScenarioRequest]:
    chosen: dict[str, ScenarioRequest] = {}
    priorities = {
        "payload_drift": ["schema_missing_key", "schema_null_injection", "schema_type_coercion"],
        "route_drift": ["route_regression", "route_invalid_path", "route_method_spoof"],
        "auth_drift": ["auth_missing_tenant", "auth_malformed_jwt", "auth_missing_token"],
    }
    grouped: dict[str, list[ScenarioRequest]] = {
        "payload_drift": [],
        "route_drift": [],
        "auth_drift": [],
    }
    for scenario in _records_to_live_scenarios(records, live_spec_path=live_spec_path):
        if scenario.scenario_type == "unknown":
            continue
        grouped.setdefault(scenario.scenario_type, []).append(scenario)

    for category, options in grouped.items():
        if not options:
            continue
        preferred = priorities.get(category, [])
        selected = next(
            (item for raw in preferred for item in options if item.raw_scenario_type == raw),
            options[0],
        )
        chosen[category] = selected
    return [chosen[key] for key in ("payload_drift", "route_drift", "auth_drift") if key in chosen]


def _records_to_live_scenarios(
    records: list[dict[str, Any]],
    *,
    live_spec_path: str,
) -> list[ScenarioRequest]:
    scenarios: list[ScenarioRequest] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        status_code = record.get("error_code") or record.get("status_code")
        method = record.get("method")
        target_url = record.get("target_url")
        raw_scenario = record.get("scenario_type")
        if not isinstance(method, str) or not isinstance(target_url, str):
            continue
        category = map_scenario_to_category(
            raw_scenario if isinstance(raw_scenario, str) else None,
            status_code=int(status_code) if isinstance(status_code, int) else None,
            error_message=record.get("actual_server_response")
            if isinstance(record.get("actual_server_response"), str)
            else None,
        )
        if category == "unknown":
            continue
        scenarios.append(
            ScenarioRequest(
                scenario_type=category,
                raw_scenario_type=raw_scenario if isinstance(raw_scenario, str) else None,
                drift_mode=_category_to_drift_mode(category),
                method=method,
                url=target_url,
                headers=_select_headers(record),
                payload=_select_payload(record),
                local_spec_path=live_spec_path,
            )
        )
    return scenarios


def _select_headers(record: dict[str, Any]) -> dict[str, str] | None:
    headers = record.get("failed_headers") or record.get("success_headers")
    return headers if isinstance(headers, dict) else None


def _select_payload(record: dict[str, Any]) -> dict[str, Any] | None:
    payload = record.get("failed_payload") or record.get("success_payload")
    return payload if isinstance(payload, dict) else None


def _category_to_drift_mode(category: str) -> DriftMode:
    if category == "payload_drift":
        return "payload"
    if category == "route_drift":
        return "route"
    return "auth"


def _demo_jwt() -> str:
    return (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJ1c2VyIjoiZnV6emVyX2FnZW50XzAwNyIsInJvbGUiOiJhZG1pbiJ9."
        "UuceJXhdiSBpwb47N1MffwuX3vd8KFwvtNYZP8wVTTo"
    )
