from pathlib import Path

from sprint4.eval.policy_error_analysis import analyze_warmstart_vs_adaptive, persist_error_analysis
from sprint4.training.supervised_warmstart import (
    assert_no_manifest_overlap,
    run_supervised_warmstart_pipeline,
)


def _supervised_row(
    *,
    episode_id: str,
    group_id: str,
    raw_scenario_type: str,
    benchmark_partition: str,
    target_action: dict,
    input_text: str,
) -> dict:
    return {
        "episode_id": episode_id,
        "group_id": group_id,
        "input_text": input_text,
        "target_action": target_action,
        "raw_scenario_type": raw_scenario_type,
        "benchmark_partition": benchmark_partition,
        "contract_version": "v1",
        "provenance": {
            "source_name": "benchmark_episode",
            "source_record_id": episode_id,
        },
    }


def _transition_row(
    *,
    episode_id: str,
    group_id: str,
    raw_scenario_type: str,
    benchmark_partition: str,
    scenario_type: str,
    request_method: str,
    request_path: str,
    action: dict,
    success: bool,
    outcome_class: str,
    reward_total: float,
    selected_route_correct: bool = True,
) -> dict:
    return {
        "episode_id": episode_id,
        "group_id": group_id,
        "state": {
            "episode_id": episode_id,
            "scenario_type": scenario_type,
            "raw_scenario_type": raw_scenario_type,
            "benchmark_partition": benchmark_partition,
            "contract_version": "v1",
            "request_method": request_method,
            "request_path": request_path,
            "request_headers": {"x-api-key": "secret"},
            "request_query": {},
            "request_body": {"amount": 100} if benchmark_partition == "repairable" else None,
            "failure_code": 404 if benchmark_partition == "repairable" else 401,
            "failure_message": "failed",
            "failure_signals": {},
            "candidate_routes": [],
            "contract_hints": {},
            "retry_count": 0,
        },
        "action": action,
        "outcome": {
            "request_succeeded": success,
            "http_status": 200 if success else 401,
            "retry_count": 1 if benchmark_partition == "repairable" else 0,
            "selected_route_correct": selected_route_correct,
            "payload_valid": success,
            "used_hallucinated_auth": False,
            "abstained": action["action_type"] == "abstain",
            "correct_abstention": benchmark_partition == "unrecoverable" and action["action_type"] == "abstain",
            "max_retries_exceeded": False,
        },
        "reward_breakdown": {
            "reward_total": reward_total,
            "reward_success": reward_total,
            "reward_efficiency": 0.0,
            "reward_route_accuracy": 0.0,
            "reward_payload_accuracy": 0.0,
            "reward_auth_safety": 0.0,
            "reward_abstention": 0.0,
            "reward_penalty_retries": 0.0,
            "reward_penalty_hallucination": 0.0,
        },
        "success": success,
        "outcome_class": outcome_class,
        "raw_scenario_type": raw_scenario_type,
        "benchmark_partition": benchmark_partition,
        "contract_version": "v1",
        "provenance": {
            "source_name": "benchmark_episode",
            "source_record_id": episode_id,
        },
    }


def _baseline_summary() -> dict:
    return {
        "topline": {
            "success_rate": 0.3,
            "repairable_success_rate": 0.125,
            "correct_abstention_rate": 1.0,
            "average_reward": 0.0,
            "average_retry_count": 0.0,
            "hallucination_rate": 0.0,
            "wrong_route_rate": 0.0,
        },
        "safety": {"incorrect_abstain_rate": 0.0},
    }


def _adaptive_summary() -> dict:
    return {
        "topline": {
            "success_rate": 1.0,
            "repairable_success_rate": 1.0,
            "correct_abstention_rate": 1.0,
            "average_reward": 10.7,
            "average_retry_count": 0.9,
            "hallucination_rate": 0.0,
            "wrong_route_rate": 0.0,
        },
        "safety": {"incorrect_abstain_rate": 0.0},
    }


def test_manifest_overlap_guard_raises() -> None:
    try:
        assert_no_manifest_overlap(
            supervised_train_manifest={"row_descriptors": [{"group_id": "shared-1"}]},
            shared_eval_manifest={"transition_row_descriptors": [{"group_id": "shared-1"}]},
        )
    except ValueError as exc:
        assert "overlaps" in str(exc)
    else:
        raise AssertionError("Expected overlap guard to raise.")


def test_policy_error_analysis_reports_confusion_and_reward_gap(tmp_path: Path) -> None:
    supervised_rows = [
        _supervised_row(
            episode_id="train-route",
            group_id="train-route",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            target_action={"action_type": "repair_route", "target_method": "POST", "target_path": "/api/v1/payments/process"},
            input_text="scenario_type=route_drift raw_scenario_type=route_regression benchmark_partition=repairable failed_request={\"path\":\"/api/v0/payments/process\"}",
        ),
        _supervised_row(
            episode_id="train-auth",
            group_id="train-auth",
            raw_scenario_type="auth_missing_token",
            benchmark_partition="unrecoverable",
            target_action={"action_type": "abstain"},
            input_text="scenario_type=auth_drift raw_scenario_type=auth_missing_token benchmark_partition=unrecoverable",
        ),
    ]
    shared_eval_manifest = {
        "manifest_id": "shared-eval-1",
        "transition_row_descriptors": [{"group_id": "eval-route"}, {"group_id": "eval-auth"}],
        "supervised_row_descriptors": [],
    }
    transition_rows = [
        _transition_row(
            episode_id="eval-route",
            group_id="eval-route",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            scenario_type="route_drift",
            request_method="POST",
            request_path="/api/v0/payments/process",
            action={"action_type": "repair_route", "target_method": "POST", "target_path": "/api/v1/payments/process"},
            success=True,
            outcome_class="repair_success",
            reward_total=12.0,
        ),
        _transition_row(
            episode_id="eval-auth",
            group_id="eval-auth",
            raw_scenario_type="auth_missing_token",
            benchmark_partition="unrecoverable",
            scenario_type="auth_drift",
            request_method="DELETE",
            request_path="/api/v1/payments/txn-1",
            action={"action_type": "abstain"},
            success=True,
            outcome_class="correct_abstain",
            reward_total=8.0,
        ),
    ]
    supervised_manifest = {
        "manifest_id": "supervised-train-1",
        "row_descriptors": [{"group_id": "train-route"}, {"group_id": "train-auth"}],
    }
    pipeline = run_supervised_warmstart_pipeline(
        supervised_rows=supervised_rows,
        supervised_train_manifest=supervised_manifest,
        shared_eval_manifest=shared_eval_manifest,
        transition_rows=transition_rows,
        output_dir=str(tmp_path / "warmstart"),
        baseline_summary=_baseline_summary(),
        adaptive_summary=_adaptive_summary(),
    )

    adaptive_eval_rows = [
        {
            **row,
            "policy_name": "adaptive",
            "manifest_id": "shared-eval-1",
        }
        for row in pipeline["eval_run"]["eval_rows"]
    ]
    analysis = analyze_warmstart_vs_adaptive(
        model_artifact=pipeline["model_artifact"],
        supervised_train_manifest=supervised_manifest,
        shared_eval_manifest=shared_eval_manifest,
        transition_rows=transition_rows,
        warmstart_eval_rows=pipeline["eval_run"]["eval_rows"],
        adaptive_eval_rows=adaptive_eval_rows,
    )
    artifacts = persist_error_analysis(analysis=analysis, output_dir=str(tmp_path / "analysis"))

    assert analysis["row_count"] == 2
    assert analysis["action_confusion"]["repair_route"]["repair_route"] == 1
    assert analysis["scenario_support"]["route_regression"] == 1
    assert all(row["reward_gap_vs_adaptive"] >= 0.0 for row in analysis["analysis_rows"])
    assert artifacts["error_analysis_json"].endswith("warmstart_error_analysis.json")
    assert (tmp_path / "analysis" / "action_confusion.json").exists()
