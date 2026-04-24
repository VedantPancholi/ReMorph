from sprint4.eval.metrics import (
    compute_metrics_by_partition,
    compute_metrics_by_scenario,
    compute_safety_metrics,
    compute_topline_metrics,
    summarize_eval_run,
)


def _eval_row(
    *,
    manifest_id: str,
    policy_name: str,
    group_id: str,
    episode_id: str,
    scenario_type: str,
    raw_scenario_type: str,
    benchmark_partition: str,
    source_name: str,
    success: bool,
    outcome_class: str,
    retries_used: int,
    reward_total: float,
    hallucination_detected: bool = False,
    wrong_route_detected: bool = False,
) -> dict:
    return {
        "manifest_id": manifest_id,
        "group_id": group_id,
        "episode_id": episode_id,
        "policy_name": policy_name,
        "scenario_type": scenario_type,
        "raw_scenario_type": raw_scenario_type,
        "benchmark_partition": benchmark_partition,
        "contract_version": "v1",
        "source_name": source_name,
        "source_record_id": episode_id,
        "success": success,
        "outcome_class": outcome_class,
        "retries_used": retries_used,
        "hallucination_detected": hallucination_detected,
        "wrong_route_detected": wrong_route_detected,
        "reward_breakdown": {"reward_total": reward_total},
    }


def test_metrics_compute_topline_and_safety_correctly() -> None:
    rows = [
        _eval_row(
            manifest_id="m1",
            policy_name="adaptive",
            group_id="g1",
            episode_id="ep1",
            scenario_type="route_drift",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            source_name="benchmark_episode",
            success=True,
            outcome_class="repair_success",
            retries_used=1,
            reward_total=12.0,
        ),
        _eval_row(
            manifest_id="m1",
            policy_name="adaptive",
            group_id="g2",
            episode_id="ep2",
            scenario_type="auth_drift",
            raw_scenario_type="auth_missing_token",
            benchmark_partition="unrecoverable",
            source_name="phase1",
            success=True,
            outcome_class="correct_abstain",
            retries_used=0,
            reward_total=8.0,
        ),
        _eval_row(
            manifest_id="m1",
            policy_name="adaptive",
            group_id="g3",
            episode_id="ep3",
            scenario_type="payload_drift",
            raw_scenario_type="schema_missing_key",
            benchmark_partition="repairable",
            source_name="phase1",
            success=False,
            outcome_class="incorrect_abstain",
            retries_used=2,
            reward_total=-9.0,
            hallucination_detected=True,
            wrong_route_detected=True,
        ),
    ]

    topline = compute_topline_metrics(rows)
    safety = compute_safety_metrics(rows)

    assert topline["success_rate"] == 0.6667
    assert topline["repairable_success_rate"] == 0.5
    assert topline["correct_abstention_rate"] == 1.0
    assert topline["hallucination_rate"] == 0.3333
    assert topline["wrong_route_rate"] == 0.3333
    assert safety["unsafe_auth_hallucination_count"] == 1
    assert safety["incorrect_abstain_count"] == 1
    assert safety["max_retry_exhaustion_count"] == 1


def test_metrics_compute_slice_breakdowns() -> None:
    rows = [
        _eval_row(
            manifest_id="m1",
            policy_name="baseline",
            group_id="g1",
            episode_id="ep1",
            scenario_type="route_drift",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            source_name="benchmark_episode",
            success=True,
            outcome_class="repair_success",
            retries_used=1,
            reward_total=12.0,
        ),
        _eval_row(
            manifest_id="m1",
            policy_name="baseline",
            group_id="g2",
            episode_id="ep2",
            scenario_type="auth_drift",
            raw_scenario_type="auth_missing_token",
            benchmark_partition="unrecoverable",
            source_name="phase1",
            success=False,
            outcome_class="unrecoverable_failure",
            retries_used=0,
            reward_total=-4.0,
        ),
    ]

    by_scenario = compute_metrics_by_scenario(rows)
    by_partition = compute_metrics_by_partition(rows)
    summary = summarize_eval_run(rows)

    assert by_scenario["route_regression"]["success_rate"] == 1.0
    assert by_partition["repairable"]["row_count"] == 1
    assert by_partition["unrecoverable"]["average_reward"] == -4.0
    assert summary["manifest_ids"] == ["m1"]
    assert summary["policy_names"] == ["baseline"]
