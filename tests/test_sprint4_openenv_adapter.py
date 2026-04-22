from sprint4.env.openenv_adapter import OpenEnvAPIEnvironment


class _FakeOpenEnvClient:
    def __init__(self) -> None:
        self.last_action = None

    def step(self, action):
        self.last_action = action
        if action.get("type") == "http_request":
            return {"status_code": 404, "success": False, "error_message": "route mismatch"}
        return {"status_code": 200, "success": True, "message": "ok"}

    def reset(self):
        return {"ok": True}

    def state(self):
        return {
            "expected_route_by_method": {"GET": "/api/v2/finance/ledger"},
            "allowed_payload_fields": {"/users": ["user"]},
        }


def test_openenv_adapter_normalizes_http_step_result() -> None:
    env = OpenEnvAPIEnvironment(client=_FakeOpenEnvClient(), baseline_contract={"paths": {}})
    response = env.execute_request("GET", "https://mock.example.com/api/v1/transactions")
    assert response.status_code == 404
    assert response.success is False


def test_openenv_adapter_exposes_state_helpers() -> None:
    env = OpenEnvAPIEnvironment(client=_FakeOpenEnvClient(), baseline_contract={"paths": {}})
    expected = env.expected_route_for_method("GET")
    hallucinated = env.is_payload_hallucinated({"rogue": "field"}, "/users")
    assert expected == "/api/v2/finance/ledger"
    assert hallucinated is True

