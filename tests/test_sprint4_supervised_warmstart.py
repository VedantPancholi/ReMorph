from sprint4.training.supervised_warmstart import (
    actions_match,
    evaluate_warmstart_on_manifest,
    predict_action,
    run_supervised_warmstart_pipeline,
    train_supervised_warmstart,
)
from sprint4.training.split_strategy import build_group_id


def _supervised_row(
    *,
    episode_id: str,
    raw_scenario_type: str,
    benchmark_partition: str,
    action_type: str,
    input_text: str,
    target_action: dict | None = None,
) -> dict:
    return {
        "episode_id": episode_id,
        "input_text": input_text,
        "target_action": target_action or {"action_type": action_type},
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
    raw_scenario_type: str,
    benchmark_partition: str,
    scenario_type: str,
    request_method: str,
    request_path: str,
    success: bool,
    outcome_class: str,
    action: dict,
    reward_total: float,
) -> dict:
    return {
        "episode_id": episode_id,
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
            "retry_count": 0,
            "selected_route_correct": True,
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


def test_train_supervised_warmstart_filters_to_manifest_groups() -> None:
    rows = [
        _supervised_row(
            episode_id="ep-1",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            action_type="repair_route",
            input_text="scenario_type=route_drift raw_scenario_type=route_regression benchmark_partition=repairable",
            target_action={"action_type": "repair_route", "target_method": "POST", "target_path": "/api/v1/payments/process"},
        ),
        _supervised_row(
            episode_id="ep-2",
            raw_scenario_type="auth_missing_token",
            benchmark_partition="unrecoverable",
            action_type="abstain",
            input_text="scenario_type=auth_drift raw_scenario_type=auth_missing_token benchmark_partition=unrecoverable",
        ),
    ]
    manifest = {
        "manifest_id": "supervised-train-1",
        "row_descriptors": [{"group_id": "ep-1"}],
    }

    model = train_supervised_warmstart(supervised_rows=rows, supervised_train_manifest=manifest)

    assert model["training_row_count"] == 1
    assert model["label_distribution"] == {"repair_route": 1}


def test_predict_action_returns_matching_route_action() -> None:
    rows = [
        _supervised_row(
            episode_id="ep-1",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            action_type="repair_route",
            input_text="scenario_type=route_drift raw_scenario_type=route_regression benchmark_partition=repairable failed_request={\"path\":\"/api/v0/payments/process\"}",
            target_action={"action_type": "repair_route", "target_method": "POST", "target_path": "/api/v1/payments/process"},
        ),
    ]
    manifest = {
        "manifest_id": "supervised-train-1",
        "row_descriptors": [{"group_id": "ep-1"}],
    }
    model = train_supervised_warmstart(supervised_rows=rows, supervised_train_manifest=manifest)

    prediction = predict_action(
        model,
        {
            "episode_id": "eval-1",
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
            "retry_count": 0,
        },
    )

    assert prediction.action_type == "repair_route"
    assert prediction.target_path == "/api/v1/payments/process"


def test_evaluate_warmstart_on_manifest_scores_offline_replay() -> None:
    supervised_rows = [
        _supervised_row(
            episode_id="route-train",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            action_type="repair_route",
            input_text="scenario_type=route_drift raw_scenario_type=route_regression benchmark_partition=repairable",
            target_action={"action_type": "repair_route", "target_method": "POST", "target_path": "/api/v1/payments/process"},
        ),
        _supervised_row(
            episode_id="auth-train",
            raw_scenario_type="auth_missing_token",
            benchmark_partition="unrecoverable",
            action_type="abstain",
            input_text="scenario_type=auth_drift raw_scenario_type=auth_missing_token benchmark_partition=unrecoverable",
        ),
    ]
    train_manifest = {
        "manifest_id": "supervised-train-1",
        "row_descriptors": [{"group_id": "route-train"}, {"group_id": "auth-train"}],
    }
    model = train_supervised_warmstart(supervised_rows=supervised_rows, supervised_train_manifest=train_manifest)
    transition_rows = [
        _transition_row(
            episode_id="route-eval",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            scenario_type="route_drift",
            request_method="POST",
            request_path="/api/v0/payments/process",
            success=True,
            outcome_class="repair_success",
            action={"action_type": "repair_route", "target_method": "POST", "target_path": "/api/v1/payments/process"},
            reward_total=12.0,
        ),
        _transition_row(
            episode_id="auth-eval",
            raw_scenario_type="auth_missing_token",
            benchmark_partition="unrecoverable",
            scenario_type="auth_drift",
            request_method="DELETE",
            request_path="/api/v1/payments/txn-1",
            success=True,
            outcome_class="correct_abstain",
            action={"action_type": "abstain"},
            reward_total=8.0,
        ),
    ]
    shared_eval_manifest = {
        "manifest_id": "shared-1",
        "transition_row_descriptors": [{"group_id": build_group_id(row)} for row in transition_rows],
    }

    result = evaluate_warmstart_on_manifest(
        model_artifact=model,
        shared_eval_manifest=shared_eval_manifest,
        transition_rows=transition_rows,
        policy_name="warmstart",
    )

    assert result["manifest_id"] == "shared-1"
    assert result["summary"]["topline"]["success_rate"] == 1.0
    assert {row["policy_name"] for row in result["eval_rows"]} == {"warmstart"}


def test_actions_match_requires_structural_match() -> None:
    assert actions_match(
        {"action_type": "repair_route", "target_method": "POST", "target_path": "/good"},
        {"action_type": "repair_route", "target_method": "POST", "target_path": "/good"},
    )
    assert not actions_match(
        {"action_type": "repair_route", "target_method": "POST", "target_path": "/bad"},
        {"action_type": "repair_route", "target_method": "POST", "target_path": "/good"},
    )


def test_run_supervised_warmstart_pipeline_persists_artifacts(tmp_path) -> None:
    supervised_rows = [
        _supervised_row(
            episode_id="route-train",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            action_type="repair_route",
            input_text="scenario_type=route_drift raw_scenario_type=route_regression benchmark_partition=repairable",
            target_action={"action_type": "repair_route", "target_method": "POST", "target_path": "/api/v1/payments/process"},
        ),
        _supervised_row(
            episode_id="auth-train",
            raw_scenario_type="auth_missing_token",
            benchmark_partition="unrecoverable",
            action_type="abstain",
            input_text="scenario_type=auth_drift raw_scenario_type=auth_missing_token benchmark_partition=unrecoverable",
        ),
    ]
    supervised_manifest = {
        "manifest_id": "supervised-train-1",
        "row_descriptors": [{"group_id": "route-train"}, {"group_id": "auth-train"}],
    }
    transition_rows = [
        _transition_row(
            episode_id="route-eval",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            scenario_type="route_drift",
            request_method="POST",
            request_path="/api/v0/payments/process",
            success=True,
            outcome_class="repair_success",
            action={"action_type": "repair_route", "target_method": "POST", "target_path": "/api/v1/payments/process"},
            reward_total=12.0,
        ),
        _transition_row(
            episode_id="auth-eval",
            raw_scenario_type="auth_missing_token",
            benchmark_partition="unrecoverable",
            scenario_type="auth_drift",
            request_method="DELETE",
            request_path="/api/v1/payments/txn-1",
            success=True,
            outcome_class="correct_abstain",
            action={"action_type": "abstain"},
            reward_total=8.0,
        ),
    ]
    shared_eval_manifest = {
        "manifest_id": "shared-1",
        "transition_row_descriptors": [{"group_id": build_group_id(row)} for row in transition_rows],
    }

    result = run_supervised_warmstart_pipeline(
        supervised_rows=supervised_rows,
        supervised_train_manifest=supervised_manifest,
        shared_eval_manifest=shared_eval_manifest,
        transition_rows=transition_rows,
        output_dir=str(tmp_path / "warmstart"),
        baseline_summary={"topline": {"success_rate": 0.4, "repairable_success_rate": 0.25, "correct_abstention_rate": 1.0, "average_reward": 1.6, "average_retry_count": 0.0, "hallucination_rate": 0.0, "wrong_route_rate": 0.0}, "safety": {"incorrect_abstain_rate": 0.0}},
        adaptive_summary={"topline": {"success_rate": 1.0, "repairable_success_rate": 1.0, "correct_abstention_rate": 1.0, "average_reward": 10.7, "average_retry_count": 0.8, "hallucination_rate": 0.0, "wrong_route_rate": 0.0}, "safety": {"incorrect_abstain_rate": 0.0}},
    )

    assert result["comparison"]["manifest_ids"] == ["shared-1"]
    assert (tmp_path / "warmstart" / "model_artifact.json").exists()
    assert (tmp_path / "warmstart" / "comparison_vs_pretraining.md").exists()
