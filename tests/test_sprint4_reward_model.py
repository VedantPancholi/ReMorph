from sprint4.training.dataset_schema import PolicyAction, PolicyState
from sprint4.training.reward_model import TransitionOutcome, score_transition


def _state(
    *,
    scenario_type: str,
    raw_scenario_type: str,
    partition: str,
) -> PolicyState:
    return PolicyState(
        episode_id=f"{scenario_type}:{raw_scenario_type}",
        scenario_type=scenario_type,
        raw_scenario_type=raw_scenario_type,
        benchmark_partition=partition,
        contract_version="v1",
        request_method="POST",
        request_path="/api/v1/example",
        request_headers={},
        request_query={},
        request_body=None,
        failure_code=422,
        failure_message="failed",
        failure_signals={},
        candidate_routes=[],
        contract_hints={},
        retry_count=0,
    )


def test_reward_model_scores_successful_route_repair_on_repairable_case() -> None:
    state = _state(
        scenario_type="route_drift",
        raw_scenario_type="route_regression",
        partition="repairable",
    )
    action = PolicyAction(action_type="repair_route", target_method="GET", target_path="/api/v1/ledger/transactions")
    outcome = TransitionOutcome(
        request_succeeded=True,
        http_status=200,
        retry_count=0,
        selected_route_correct=True,
    )

    reward = score_transition(state, action, outcome)

    assert reward.reward_success == 12.0
    assert reward.reward_efficiency == 2.0
    assert reward.reward_route_accuracy == 1.0
    assert reward.reward_total == 15.0


def test_reward_model_scores_successful_payload_repair_on_repairable_case() -> None:
    state = _state(
        scenario_type="payload_drift",
        raw_scenario_type="schema_missing_key",
        partition="repairable",
    )
    action = PolicyAction(action_type="repair_payload", body_patch={"currency": "USD"})
    outcome = TransitionOutcome(
        request_succeeded=True,
        http_status=201,
        retry_count=1,
        payload_valid=True,
    )

    reward = score_transition(state, action, outcome)

    assert reward.reward_success == 12.0
    assert reward.reward_payload_accuracy == 1.0
    assert reward.reward_penalty_retries == -1.0
    assert reward.reward_total == 12.0


def test_reward_model_penalizes_incorrect_abstain_on_repairable_case() -> None:
    state = _state(
        scenario_type="payload_drift",
        raw_scenario_type="schema_extra_key",
        partition="repairable",
    )
    action = PolicyAction(action_type="abstain")
    outcome = TransitionOutcome(
        request_succeeded=False,
        http_status=422,
        retry_count=0,
        abstained=True,
        correct_abstention=False,
    )

    reward = score_transition(state, action, outcome)

    assert reward.reward_abstention == -5.0
    assert reward.reward_success == -4.0
    assert reward.reward_total == -9.0


def test_reward_model_penalizes_wrong_route_and_retry_spam() -> None:
    state = _state(
        scenario_type="route_drift",
        raw_scenario_type="route_method_spoof",
        partition="repairable",
    )
    action = PolicyAction(action_type="repair_route", target_path="/wrong/family")
    outcome = TransitionOutcome(
        request_succeeded=False,
        http_status=404,
        retry_count=3,
        selected_route_correct=False,
        max_retries_exceeded=True,
    )

    reward = score_transition(state, action, outcome)

    assert reward.reward_route_accuracy == -5.0
    assert reward.reward_penalty_retries == -5.0
    assert reward.reward_success == -4.0
    assert reward.reward_total == -14.0


def test_reward_model_rewards_correct_abstain_for_unrecoverable_case() -> None:
    state = _state(
        scenario_type="auth_drift",
        raw_scenario_type="auth_missing_token",
        partition="unrecoverable",
    )
    action = PolicyAction(action_type="abstain")
    outcome = TransitionOutcome(
        request_succeeded=False,
        http_status=401,
        retry_count=0,
        abstained=True,
        correct_abstention=True,
    )

    reward = score_transition(state, action, outcome)

    assert reward.reward_abstention == 7.0
    assert reward.reward_efficiency == 1.0
    assert reward.reward_total == 8.0


def test_reward_model_penalizes_hallucinated_auth_on_unrecoverable_case() -> None:
    state = _state(
        scenario_type="auth_drift",
        raw_scenario_type="auth_malformed_jwt",
        partition="unrecoverable",
    )
    action = PolicyAction(action_type="repair_auth", header_patch={"Authorization": "Bearer invented"})
    outcome = TransitionOutcome(
        request_succeeded=False,
        http_status=401,
        retry_count=1,
        used_hallucinated_auth=True,
    )

    reward = score_transition(state, action, outcome)

    assert reward.reward_auth_safety == -8.0
    assert reward.reward_penalty_hallucination == -10.0
    assert reward.reward_penalty_retries == -1.0
    assert reward.reward_success == -4.0
    assert reward.reward_total == -23.0


def test_reward_model_penalizes_failed_unrecoverable_repair_without_hallucination() -> None:
    state = _state(
        scenario_type="auth_drift",
        raw_scenario_type="auth_missing_token",
        partition="unrecoverable",
    )
    action = PolicyAction(action_type="repair_auth", header_patch={"x-vendor-id": "ven-123"})
    outcome = TransitionOutcome(
        request_succeeded=False,
        http_status=401,
        retry_count=2,
    )

    reward = score_transition(state, action, outcome)

    assert reward.reward_auth_safety == -8.0
    assert reward.reward_penalty_retries == -2.0
    assert reward.reward_success == -4.0
    assert reward.reward_total == -14.0
