from pathlib import Path

from sprint4.training.supervised_warmstart import predict_action, train_supervised_warmstart
from sprint4.training.targeted_refinement import build_refinement_plan, run_targeted_refinement_pipeline


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
            "request_body": {"amount": 100},
            "failure_code": 404,
            "failure_message": "failed",
            "failure_signals": {},
            "candidate_routes": [],
            "contract_hints": {},
            "retry_count": 1,
        },
        "action": action,
        "outcome": {
            "request_succeeded": success,
            "http_status": 200 if success else 400,
            "retry_count": 1,
            "selected_route_correct": success,
            "payload_valid": success,
            "used_hallucinated_auth": False,
            "abstained": False,
            "correct_abstention": False,
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


def _query_state() -> dict:
    return {
        "episode_id": "eval-route",
        "scenario_type": "route_drift",
        "raw_scenario_type": "route_regression",
        "benchmark_partition": "repairable",
        "contract_version": "v1",
        "request_method": "POST",
        "request_path": "/api/v0/payments/process",
        "request_headers": {},
        "request_query": {},
        "request_body": {"amount": 100},
        "failure_code": 404,
        "failure_message": "failed",
        "failure_signals": {},
        "candidate_routes": [],
        "contract_hints": {},
        "retry_count": 1,
    }


def test_build_refinement_plan_surfaces_focus_weights() -> None:
    analysis = {
        "missed_by_scenario": {"route_regression": 2, "schema_missing_key": 1},
        "wrong_route_repairs": {"route_regression": 1},
        "payload_repair_failures": {"schema_missing_key": 1},
        "action_confusion": {
            "repair_route": {"repair_payload": 2},
            "repair_payload": {"repair_payload": 1},
        },
        "analysis_rows": [
            {"raw_scenario_type": "route_regression", "reward_gap_vs_adaptive": 22.0},
            {"raw_scenario_type": "route_regression", "reward_gap_vs_adaptive": 12.0},
            {"raw_scenario_type": "schema_missing_key", "reward_gap_vs_adaptive": 8.0},
        ],
    }
    transition_rows = [
        _transition_row(
            episode_id="route-train-1",
            group_id="route-train-1",
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
    ]

    plan = build_refinement_plan(error_analysis=analysis, transition_rows=transition_rows)

    assert plan["focus_scenarios"][0] == "route_regression"
    assert plan["scenario_weight_overrides"]["route_regression"] > plan["scenario_weight_overrides"]["schema_missing_key"]
    assert plan["action_weight_overrides"]["repair_route"] > 1.0
    assert plan["recommended_top_k"] == 3
    assert plan["reward_priors_by_group"]["route-train-1"] == 12.0


def test_targeted_refinement_reweights_toward_missed_action_family(tmp_path: Path) -> None:
    supervised_rows = [
        _supervised_row(
            episode_id="payload-1",
            group_id="payload-1",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            target_action={"action_type": "repair_payload", "body_patch": {"amount": 100}},
            input_text="scenario_type=route_drift raw_scenario_type=route_regression benchmark_partition=repairable failed_request path /api/v0/payments/process amount field",
        ),
        _supervised_row(
            episode_id="route-1",
            group_id="route-1",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            target_action={"action_type": "repair_route", "target_method": "POST", "target_path": "/api/v1/payments/process"},
            input_text="scenario_type=route_drift raw_scenario_type=route_regression benchmark_partition=repairable failed_request path /api/v0/payments/process",
        ),
        _supervised_row(
            episode_id="route-2",
            group_id="route-2",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            target_action={"action_type": "repair_route", "target_method": "POST", "target_path": "/api/v1/payments/process"},
            input_text="scenario_type=route_drift raw_scenario_type=route_regression benchmark_partition=repairable failed_request path /api/v0/payments/process",
        ),
    ]
    supervised_manifest = {
        "manifest_id": "supervised-train-1",
        "row_descriptors": [{"group_id": "payload-1"}, {"group_id": "route-1"}, {"group_id": "route-2"}],
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
    ]
    shared_eval_manifest = {
        "manifest_id": "shared-1",
        "transition_row_descriptors": [{"group_id": "eval-route"}],
        "supervised_row_descriptors": [],
    }
    error_analysis = {
        "missed_by_scenario": {"route_regression": 1},
        "wrong_route_repairs": {"route_regression": 1},
        "payload_repair_failures": {},
        "action_confusion": {"repair_route": {"repair_payload": 1}},
        "analysis_rows": [
            {"raw_scenario_type": "route_regression", "reward_gap_vs_adaptive": 22.0},
        ],
    }

    baseline_model = train_supervised_warmstart(
        supervised_rows=supervised_rows,
        supervised_train_manifest=supervised_manifest,
    )
    baseline_prediction = predict_action(baseline_model, _query_state())

    result = run_targeted_refinement_pipeline(
        supervised_rows=supervised_rows,
        supervised_train_manifest=supervised_manifest,
        shared_eval_manifest=shared_eval_manifest,
        transition_rows=transition_rows,
        error_analysis=error_analysis,
        output_dir=str(tmp_path / "refined"),
        warmstart_summary={
            "topline": {
                "success_rate": 0.5,
                "repairable_success_rate": 0.5,
                "correct_abstention_rate": 1.0,
                "average_reward": 0.7,
                "average_retry_count": 1.0,
                "hallucination_rate": 0.0,
                "wrong_route_rate": 0.5,
            },
            "safety": {"incorrect_abstain_rate": 0.0},
        },
    )

    refined_prediction = predict_action(result["model_artifact"], _query_state())

    assert baseline_prediction.action_type == "repair_payload"
    assert refined_prediction.action_type == "repair_route"
    assert result["refinement_plan"]["scenario_weight_overrides"]["route_regression"] > 1.0
    assert result["comparison"]["policies"][-1]["policy_name"] == "warmstart_refined"
    assert result["adoption_decision"]["recommended_policy"] == "warmstart_refined"
    assert (tmp_path / "refined" / "refinement_plan.json").exists()
    assert (tmp_path / "refined" / "comparison_vs_warmstart.md").exists()
