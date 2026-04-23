from sprint4.env.live_api_env import LiveAPIEnvironment
from sprint4.env.live_support import map_scenario_to_category


class _FakeResponse:
    def __init__(self, *, status_code: int, text: str, reason_phrase: str = "error") -> None:
        self.status_code = status_code
        self.text = text
        self.reason_phrase = reason_phrase


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self._response


def test_live_api_env_normalizes_422_validation_failures() -> None:
    client = _FakeClient(
        _FakeResponse(
            status_code=422,
            reason_phrase="unprocessable entity",
            text='{"detail":[{"type":"missing","loc":["body","currency"],"msg":"Field required"}]}',
        )
    )
    env = LiveAPIEnvironment(
        base_url="http://127.0.0.1:8000",
        baseline_contract={"paths": {}},
        client=client,
    )

    response = env.execute_request(
        "POST",
        "/api/v1/payments/process",
        headers={"x-api-key": "secret"},
        payload={"amount": 100},
    )

    assert response.success is False
    assert response.status_code == 422
    assert response.message == "Field required"
    assert response.metadata["scenario_type"] == "payload_drift"
    assert response.metadata["failure_signals"]["missing_fields"] == ["currency"]


def test_map_scenario_to_category_handles_rich_live_labels() -> None:
    assert map_scenario_to_category("schema_missing_key") == "payload_drift"
    assert map_scenario_to_category("route_regression") == "route_drift"
    assert map_scenario_to_category("jwt_missing") == "auth_drift"
