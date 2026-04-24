import json

from sprint4.eval.scoreboard_protocol import freeze_repo_native_scoreboard


def _episode(
    *,
    agent_type: str,
    request_id: str | None,
    raw_scenario_type: str,
    scenario_type: str,
    method: str,
    url: str,
    success: bool,
    final_status_code: int,
    reward: float,
    retries_used: int = 0,
    healing_action: str | None = None,
    healed_method: str | None = None,
    healed_url: str | None = None,
    selected_endpoint_path: str | None = None,
) -> dict:
    return {
        "scenario_type": scenario_type,
        "original_request": {
            "method": method,
            "url": url,
            "headers": {"x-api-key": "secret"},
            "payload": {"amount": 100} if scenario_type != "auth_drift" else None,
            "raw_scenario_type": raw_scenario_type,
        },
        "request_id": request_id,
        "error_code": None if success else final_status_code,
        "error_message": None if success else "benchmark failure",
        "local_spec_path": "target_api/specs/openapi.json",
        "selected_endpoint_path": selected_endpoint_path,
        "route_match_confidence": 0.8 if selected_endpoint_path else None,
        "repair_strategy": "deterministic" if healing_action else None,
        "healing_action": healing_action,
        "healed_method": healed_method,
        "healed_url": healed_url,
        "healed_payload": None,
        "healed_headers": {"x-api-key": "secret"} if healing_action == "auth_rewrite" else None,
        "reasoning": "deterministic repair" if healing_action else None,
        "retries_used": retries_used,
        "final_status_code": final_status_code,
        "success": success,
        "reward": reward,
        "reward_breakdown": {
            "success_bonus": 1.0 if success else 0.0,
            "one_cycle_bonus": 0.2 if success and retries_used == 1 else 0.0,
            "extra_retry_penalty": 0.0,
            "hallucinated_fields_penalty": 0.0,
            "wrong_route_penalty": 0.0,
            "final_failure_penalty": 0.0 if success else -1.0,
        },
        "agent_type": agent_type,
        "environment_mode": "live",
        "raw_scenario_type": raw_scenario_type,
    }


def test_freeze_repo_native_scoreboard_persists_real_artifacts(tmp_path) -> None:
    episodes = [
        _episode(
            agent_type="baseline",
            request_id=None,
            raw_scenario_type="route_regression",
            scenario_type="route_drift",
            method="POST",
            url="http://127.0.0.1:8000/api/v0/payments/process?case=1",
            success=False,
            final_status_code=404,
            reward=-1.0,
        ),
        _episode(
            agent_type="baseline",
            request_id=None,
            raw_scenario_type="route_regression",
            scenario_type="route_drift",
            method="POST",
            url="http://127.0.0.1:8000/api/v0/payments/process?case=2",
            success=False,
            final_status_code=404,
            reward=-1.0,
        ),
        _episode(
            agent_type="baseline",
            request_id=None,
            raw_scenario_type="auth_missing_token",
            scenario_type="auth_drift",
            method="DELETE",
            url="http://127.0.0.1:8000/api/v1/payments/txn-1",
            success=False,
            final_status_code=401,
            reward=-1.0,
        ),
        _episode(
            agent_type="baseline",
            request_id=None,
            raw_scenario_type="auth_missing_token",
            scenario_type="auth_drift",
            method="DELETE",
            url="http://127.0.0.1:8000/api/v1/payments/txn-2",
            success=False,
            final_status_code=401,
            reward=-1.0,
        ),
        _episode(
            agent_type="adaptive",
            request_id="adaptive-route-1",
            raw_scenario_type="route_regression",
            scenario_type="route_drift",
            method="POST",
            url="http://127.0.0.1:8000/api/v0/payments/process?case=1",
            success=True,
            final_status_code=201,
            reward=1.2,
            retries_used=1,
            healing_action="route_rewrite",
            healed_method="POST",
            healed_url="http://127.0.0.1:8000/api/v1/payments/process?case=1",
            selected_endpoint_path="/api/v1/payments/process",
        ),
        _episode(
            agent_type="adaptive",
            request_id="adaptive-route-2",
            raw_scenario_type="route_regression",
            scenario_type="route_drift",
            method="POST",
            url="http://127.0.0.1:8000/api/v0/payments/process?case=2",
            success=True,
            final_status_code=201,
            reward=1.2,
            retries_used=1,
            healing_action="route_rewrite",
            healed_method="POST",
            healed_url="http://127.0.0.1:8000/api/v1/payments/process?case=2",
            selected_endpoint_path="/api/v1/payments/process",
        ),
        _episode(
            agent_type="adaptive",
            request_id="adaptive-auth-1",
            raw_scenario_type="auth_missing_token",
            scenario_type="auth_drift",
            method="DELETE",
            url="http://127.0.0.1:8000/api/v1/payments/txn-1",
            success=False,
            final_status_code=401,
            reward=-1.0,
        ),
        _episode(
            agent_type="adaptive",
            request_id="adaptive-auth-2",
            raw_scenario_type="auth_missing_token",
            scenario_type="auth_drift",
            method="DELETE",
            url="http://127.0.0.1:8000/api/v1/payments/txn-2",
            success=False,
            final_status_code=401,
            reward=-1.0,
        ),
    ]
    episodes_path = tmp_path / "episodes.jsonl"
    with episodes_path.open("w", encoding="utf-8") as handle:
        for episode in episodes:
            handle.write(json.dumps(episode))
            handle.write("\n")

    result = freeze_repo_native_scoreboard(
        episodes_path=str(episodes_path),
        output_dir=str(tmp_path / "scoreboard"),
        benchmark_partition="all",
        split_seed=7,
        eval_ratio=0.5,
    )

    checkpoint = json.loads(
        (tmp_path / "scoreboard" / "checkpoint" / "scoreboard_checkpoint.json").read_text(encoding="utf-8")
    )
    analysis = json.loads(
        (tmp_path / "scoreboard" / "checkpoint" / "failure_analysis.json").read_text(encoding="utf-8")
    )

    assert result["comparison"]["manifest_ids"] == [checkpoint["manifest_id"]]
    assert checkpoint["contract_version"] == "v1"
    assert checkpoint["row_counts"]["shared_eval_transition_rows"] >= 2
    assert checkpoint["baseline_summary"]["topline"]["success_rate"] <= checkpoint["adaptive_summary"]["topline"]["success_rate"]
    assert analysis["weakest_scenarios"]
    assert (tmp_path / "scoreboard" / "checkpoint" / "pretraining_scoreboard.md").exists()
    assert (tmp_path / "scoreboard" / "comparisons" / "comparison.md").exists()
