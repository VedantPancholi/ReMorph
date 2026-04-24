import json

from remorph_client import ReMorphClient
from remorph_client.config import ReMorphClientConfig
from sprint4.env.interfaces import APIEnvironment
from sprint4.env.mutable_api_env import EnvironmentResponse


class _FakeEnv(APIEnvironment):
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def reset(self) -> None:
        return None

    def apply_drift(self, drift_mode: str) -> None:
        return None

    def execute_request(self, method: str, url: str, *, headers=None, payload=None):
        self.calls.append((method, url, headers, payload))
        return self._responses.pop(0)

    def expected_route_for_method(self, method: str) -> str | None:
        return "/users"

    def is_payload_hallucinated(self, payload: dict[str, str], route: str) -> bool:
        return False


def test_remorph_client_loads_yaml_config(tmp_path) -> None:
    config_path = tmp_path / "remorph.yaml"
    config_path.write_text(
        json.dumps(
            {
                "base_url": "http://127.0.0.1:8000",
                "openapi_spec_path": "target_api/specs/openapi.json",
                "auth": {"headers": {"Authorization": "Bearer token"}},
                "safe_mode": True,
                "max_retries": 2,
            }
        ).replace("{", "").replace("}", ""),
        encoding="utf-8",
    )

    config_path.write_text(
        "base_url: http://127.0.0.1:8000\n"
        "openapi_spec_path: target_api/specs/openapi.json\n"
        "auth:\n"
        "  headers:\n"
        "    Authorization: Bearer token\n"
        "safe_mode: true\n"
        "max_retries: 2\n",
        encoding="utf-8",
    )

    config = ReMorphClientConfig.from_file(str(config_path))

    assert config.base_url == "http://127.0.0.1:8000"
    assert config.auth_headers["Authorization"] == "Bearer token"
    assert config.safe_mode is True


def test_remorph_client_request_returns_safe_abstain_shape() -> None:
    client = ReMorphClient(
        ReMorphClientConfig(
            base_url="http://127.0.0.1:8000",
            openapi_spec_path="target_api/specs/openapi.json",
            safe_mode=True,
        ),
        env=_FakeEnv(
            [
                EnvironmentResponse(
                    success=False,
                    status_code=401,
                    message="Unauthorized",
                    metadata={"scenario_type": "auth_drift"},
                )
            ]
        ),
    )

    response = client.request(method="GET", path="/api/v1/payments/process")

    assert response["status"] == "safe_abstain"
    assert response["safe_abstain"] is True
    assert response["recoverable"] is False
    assert response["unrecoverable_reason"] == "missing_or_invalid_credential_material"
