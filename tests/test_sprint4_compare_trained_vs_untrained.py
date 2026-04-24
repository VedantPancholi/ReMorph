from sprint4.evaluation.compare_trained_vs_untrained import compare_trained_vs_untrained


def _episode(
    *,
    scenario_type: str,
    raw_scenario_type: str,
    success: bool,
    reward: float,
    retries_used: int,
    healing_action: str,
    recoverable: bool,
    unrecoverable_reason: str | None = None,
) -> dict:
    return {
        "scenario_type": scenario_type,
        "raw_scenario_type": raw_scenario_type,
        "original_request": {
            "method": "GET",
            "url": "http://127.0.0.1:8000/mock",
            "headers": {},
            "payload": None,
        },
        "success": success,
        "reward": reward,
        "retries_used": retries_used,
        "healing_action": healing_action,
        "recoverable": recoverable,
        "unrecoverable_reason": unrecoverable_reason,
        "final_status_code": 200 if success else 401,
        "reward_breakdown": {"final_reward": reward},
    }


def test_compare_trained_vs_untrained_marks_trained_policy_not_run_when_missing() -> None:
    comparison = compare_trained_vs_untrained(
        baseline_records=[
            _episode(
                scenario_type="route_drift",
                raw_scenario_type="route_regression",
                success=False,
                reward=-1.0,
                retries_used=0,
                healing_action="no_change",
                recoverable=True,
            )
        ],
        adaptive_records=[
            _episode(
                scenario_type="route_drift",
                raw_scenario_type="route_regression",
                success=True,
                reward=1.1,
                retries_used=1,
                healing_action="route_rewrite",
                recoverable=True,
            )
        ],
    )

    by_name = {row["policy_name"]: row for row in comparison["policies"]}
    assert by_name["trained_policy"]["status"] == "not_run"
    assert by_name["trained_policy"]["placeholder_used"] is True


def test_compare_trained_vs_untrained_uses_training_summary_when_available() -> None:
    comparison = compare_trained_vs_untrained(
        baseline_records=[],
        adaptive_records=[],
        trained_policy_summary={
            "status": "completed",
            "placeholder": False,
            "policy_metrics": {
                "success_rate": 0.75,
                "avg_reward": 1.4,
                "avg_retries": 0.5,
                "repairable_success_rate": 0.8,
                "unrecoverable_safety_rate": 1.0,
                "safe_abstention_accuracy": 1.0,
            },
            "eval_summary": {"sample_count": 4},
        },
    )

    by_name = {row["policy_name"]: row for row in comparison["policies"]}
    assert by_name["trained_policy"]["status"] == "completed"
    assert by_name["trained_policy"]["success_rate"] == 0.75
    assert by_name["trained_policy"]["safe_abstention_accuracy"] == 1.0
