from sprint4.eval.compare_policies import (
    compare_policy_runs,
    evaluate_policy_on_manifest,
    render_comparison_summary,
)


def _transition_row(
    *,
    episode_id: str,
    raw_scenario_type: str,
    benchmark_partition: str,
    success: bool,
    outcome_class: str,
    reward_total: float,
    source_name: str = "benchmark_episode",
    source_record_id: str | None = None,
    retries_used: int = 0,
    selected_route_correct: bool = True,
    used_hallucinated_auth: bool = False,
) -> dict:
    return {
        "episode_id": episode_id,
        "state": {
            "scenario_type": "route_drift" if benchmark_partition == "repairable" else "auth_drift",
            "contract_version": "v1",
            "benchmark_partition": benchmark_partition,
            "raw_scenario_type": raw_scenario_type,
        },
        "action": {"action_type": "repair_route"},
        "outcome": {
            "request_succeeded": success,
            "http_status": 200 if success else 401,
            "retry_count": retries_used,
            "selected_route_correct": selected_route_correct,
            "used_hallucinated_auth": used_hallucinated_auth,
        },
        "reward_breakdown": {"reward_total": reward_total},
        "success": success,
        "outcome_class": outcome_class,
        "raw_scenario_type": raw_scenario_type,
        "benchmark_partition": benchmark_partition,
        "contract_version": "v1",
        "provenance": {
            "source_name": source_name,
            "source_record_id": source_record_id or episode_id,
        },
    }


def test_compare_policies_evaluates_same_shared_eval_manifest() -> None:
    manifest = {
        "manifest_id": "shared-1",
        "transition_row_descriptors": [
            {"group_id": "ep-1"},
            {"group_id": "ep-2"},
        ],
    }
    adaptive_rows = [
        _transition_row(
            episode_id="ep-1",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            success=True,
            outcome_class="repair_success",
            reward_total=15.0,
        ),
        _transition_row(
            episode_id="ep-2",
            raw_scenario_type="auth_missing_token",
            benchmark_partition="unrecoverable",
            success=True,
            outcome_class="correct_abstain",
            reward_total=8.0,
        ),
    ]
    baseline_rows = [
        _transition_row(
            episode_id="ep-1",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            success=False,
            outcome_class="repair_failure",
            reward_total=-4.0,
        ),
        _transition_row(
            episode_id="ep-2",
            raw_scenario_type="auth_missing_token",
            benchmark_partition="unrecoverable",
            success=False,
            outcome_class="unrecoverable_failure",
            reward_total=-4.0,
        ),
    ]

    adaptive = evaluate_policy_on_manifest("adaptive", manifest, adaptive_rows)
    baseline = evaluate_policy_on_manifest("baseline", manifest, baseline_rows)
    comparison = compare_policy_runs([baseline, adaptive])

    assert adaptive["manifest_id"] == "shared-1"
    assert baseline["manifest_id"] == "shared-1"
    assert len(adaptive["eval_rows"]) == 2
    assert len(baseline["eval_rows"]) == 2
    assert {row["policy_name"] for row in comparison["policies"]} == {"baseline", "adaptive"}


def test_render_comparison_summary_is_human_readable() -> None:
    summary = render_comparison_summary(
        {
            "manifest_ids": ["shared-1"],
            "policies": [
                {
                    "policy_name": "baseline",
                    "overall_success": 0.2,
                    "repairable_success": 0.0,
                    "correct_abstention": 0.0,
                    "average_reward": -1.0,
                    "average_retries": 0.0,
                    "hallucination_rate": 0.0,
                    "wrong_route_rate": 0.0,
                    "incorrect_abstain_rate": 0.0,
                }
            ],
        }
    )

    assert "Policy | Overall Success" in summary
    assert "baseline" in summary
