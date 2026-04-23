from dataclasses import dataclass

from sprint4.env.scenario_loader import load_contract_bundle
from sprint4.evaluation.benchmark_runner import run_benchmark


def test_benchmark_output_shape(tmp_path) -> None:
    report = run_benchmark(
        bundle=load_contract_bundle(),
        episodes_per_scenario=1,
        output_dir=str(tmp_path),
    )
    assert "baseline" in report
    assert "adaptive" in report
    assert "deltas" in report
    assert "artifacts" in report
    assert set(report["adaptive"].keys()) >= {
        "success_rate",
        "avg_retries",
        "avg_latency_ms",
        "reward_average",
        "per_scenario_accuracy",
        "per_raw_scenario_accuracy",
    }


@dataclass
class _FakeEnvResponse:
    success: bool
    status_code: int
    message: str | None = None
    body: dict | None = None
    raw_response_text: str | None = None
    parsed_error: dict | None = None
    metadata: dict | None = None


class _FakeLiveEnv:
    def reset(self) -> None:
        return None

    def apply_drift(self, drift_mode: str) -> None:
        self._drift_mode = drift_mode

    def execute_request(self, method, url, *, headers=None, payload=None):
        if "v0" in url:
            return _FakeEnvResponse(success=False, status_code=404, message="route failed")
        return _FakeEnvResponse(success=True, status_code=200, body={"ok": True})

    def expected_route_for_method(self, method: str) -> str | None:
        return "/api/v1/ledger/transactions"

    def is_payload_hallucinated(self, payload, route: str) -> bool:
        return False


def test_benchmark_supports_live_mode_with_custom_scenarios(tmp_path, monkeypatch) -> None:
    from sprint4.env.scenario_loader import ScenarioRequest

    monkeypatch.setattr(
        "sprint4.evaluation.benchmark_runner.build_environment",
        lambda **_: _FakeLiveEnv(),
    )

    report = run_benchmark(
        bundle=load_contract_bundle(),
        scenarios=[
            ScenarioRequest(
                scenario_type="route_drift",
                raw_scenario_type="route_regression",
                drift_mode="route",
                method="GET",
                url="http://127.0.0.1:8000/api/v0/ledger/transactions",
                headers={"Authorization": "Bearer token"},
                payload=None,
                local_spec_path="target_api/specs/openapi.json",
            )
        ],
        episodes_per_scenario=1,
        output_dir=str(tmp_path),
        env_mode="live",
        live_base_url="http://127.0.0.1:8000",
    )

    assert report["metadata"]["environment_mode"] == "live"
    assert report["metadata"]["backend"] == "live"
