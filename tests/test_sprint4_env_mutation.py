from sprint4.env.mutable_api_env import MutableAPIEnvironment
from sprint4.env.scenario_loader import load_contract_bundle


def test_mutable_env_returns_expected_codes_for_each_drift_mode() -> None:
    bundle = load_contract_bundle()
    env = MutableAPIEnvironment(
        baseline_contract=bundle.baseline_contract,
        drift_contracts=bundle.drift_contracts,
    )

    env.apply_drift("payload")
    payload_fail = env.execute_request(
        "POST",
        "https://mock.example.com/users",
        headers={"Authorization": "Bearer demo-token"},
        payload={"first_name": "John", "last_name": "Doe"},
    )
    assert payload_fail.status_code == 400

    env.apply_drift("route")
    route_fail = env.execute_request(
        "GET",
        "https://mock.example.com/api/v1/transactions",
        headers={"Authorization": "Bearer demo-token"},
        payload=None,
    )
    assert route_fail.status_code == 404

    env.apply_drift("auth")
    auth_fail = env.execute_request(
        "GET",
        "https://mock.example.com/api/v2/finance/ledger",
        headers={"Authorization": "Bearer demo-token"},
        payload=None,
    )
    assert auth_fail.status_code == 401

