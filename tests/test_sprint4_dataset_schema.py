from sprint4.training.dataset_schema import (
    PolicyAction,
    PolicyState,
    RewardBreakdown,
    TransitionOutcome,
    TransitionRow,
)


def test_transition_row_accepts_typed_phase2_objects() -> None:
    state = PolicyState(
        episode_id="ep-1",
        scenario_type="payload_drift",
        raw_scenario_type="schema_missing_key",
        benchmark_partition="repairable",
        contract_version="v1",
        request_method="POST",
        request_path="/api/v1/payments/process",
        request_headers={"x-api-key": "secret"},
        request_query={},
        request_body={"amount": 100},
        failure_code=422,
        failure_message="Field required",
        failure_signals={"missing_fields": ["currency"]},
        candidate_routes=[],
        contract_hints={"selected_endpoint_path": "/api/v1/payments/process"},
        retry_count=0,
    )
    action = PolicyAction(
        action_type="repair_payload",
        target_method="POST",
        target_path="/api/v1/payments/process",
        body_patch={"amount": 100, "currency": "USD"},
        reason="Added missing required field.",
    )
    reward = RewardBreakdown(
        reward_total=10.0,
        reward_success=10.0,
        reward_payload_accuracy=1.0,
    )
    outcome = TransitionOutcome(
        request_succeeded=True,
        http_status=201,
        retry_count=1,
        payload_valid=True,
    )

    row = TransitionRow(
        episode_id="ep-1",
        state=state,
        action=action,
        outcome=outcome,
        next_state=None,
        reward_breakdown=reward,
        done=True,
        success=True,
        outcome_class="repair_success",
        raw_scenario_type="schema_missing_key",
        benchmark_partition="repairable",
        contract_version="v1",
    )

    assert row.state.request_path == "/api/v1/payments/process"
    assert row.action.action_type == "repair_payload"
    assert row.reward_breakdown.reward_total == 10.0
