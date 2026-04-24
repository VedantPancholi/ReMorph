from sprint4.training.benchmark_contract import BENCHMARK_CONTRACT_VERSION
from sprint4.training.dataset_schema import PolicyAction, PolicyState
from sprint4.training.policy_adapter import (
    build_policy_batch,
    build_policy_example,
    episode_to_rl_transition,
    episode_to_policy_action,
    episode_to_policy_state,
)


def test_episode_to_policy_state_normalizes_repairable_episode() -> None:
    episode = {
        "request_id": "ep-123",
        "scenario_type": "route_drift",
        "raw_scenario_type": "route_regression",
        "original_request": {
            "method": "GET",
            "url": "http://127.0.0.1:8000/api/v0/ledger/transactions?limit=100",
            "headers": {"Authorization": "Bearer demo-token"},
            "payload": None,
        },
        "trapped_error": {
            "retry_count": 1,
            "failure_signals": {"route_error_detail": "not found"},
            "query_params": {"start_date": "2024-01-01T00:00:00Z"},
        },
        "error_code": 404,
        "error_message": "Not found",
        "selected_endpoint_path": "/api/v1/ledger/transactions",
        "route_match_confidence": 0.75,
        "repair_strategy": "deterministic",
        "healing_action": "route_rewrite",
        "reward_breakdown": {"success_bonus": 1.0},
    }

    state = episode_to_policy_state(episode)

    assert isinstance(state, PolicyState)
    assert state.episode_id == "ep-123"
    assert state.request_method == "GET"
    assert state.request_path == "/api/v0/ledger/transactions"
    assert state.request_query["limit"] == "100"
    assert state.request_query["start_date"] == "2024-01-01T00:00:00Z"
    assert state.benchmark_partition == "repairable"
    assert state.contract_version == BENCHMARK_CONTRACT_VERSION
    assert state.candidate_routes[0].path == "/api/v1/ledger/transactions"


def test_episode_to_policy_action_returns_abstain_for_unrecoverable_episode() -> None:
    episode = {
        "raw_scenario_type": "auth_missing_token",
        "healing_action": None,
        "reasoning": None,
    }

    action = episode_to_policy_action(episode)

    assert isinstance(action, PolicyAction)
    assert action.action_type == "abstain"
    assert "unrecoverable auth scenario" in str(action.reason)


def test_build_policy_example_returns_state_and_action() -> None:
    episode = {
        "request_id": "ep-456",
        "scenario_type": "payload_drift",
        "raw_scenario_type": "schema_missing_key",
        "original_request": {
            "method": "POST",
            "url": "http://127.0.0.1:8000/api/v1/payments/process",
            "headers": {"x-api-key": "secret"},
            "payload": {"amount": 100},
        },
        "error_code": 422,
        "error_message": "Field required",
        "healing_action": "payload_rewrite",
        "healed_method": "POST",
        "healed_url": "http://127.0.0.1:8000/api/v1/payments/process",
        "healed_payload": {"amount": 100, "currency": "USD"},
        "reasoning": "Added missing currency.",
    }

    state, action = build_policy_example(episode)

    assert state.raw_scenario_type == "schema_missing_key"
    assert action.action_type == "repair_payload"
    assert action.body_patch == {"amount": 100, "currency": "USD"}


def test_build_policy_batch_keeps_partition_metadata() -> None:
    batch = build_policy_batch(
        [
            {
                "prompt": "repair this",
                "completion": '{"action":"repair"}',
                "reward": 1.2,
                "success": True,
                "scenario_type": "payload_drift",
                "raw_scenario_type": "schema_missing_key",
                "metadata": {"benchmark_partition": "repairable"},
            }
        ]
    )

    assert batch.rewards == [1.2]
    assert batch.metadata[0]["raw_scenario_type"] == "schema_missing_key"
    assert batch.metadata[0]["benchmark_partition"] == "repairable"


def test_episode_to_rl_transition_returns_rl_facing_shape() -> None:
    episode = {
        "request_id": "ep-safe",
        "scenario_type": "auth_drift",
        "raw_scenario_type": "auth_missing_token",
        "original_request": {
            "method": "GET",
            "url": "http://127.0.0.1:8000/api/v1/ledger/transactions",
            "headers": {},
            "payload": None,
        },
        "error_code": 401,
        "error_message": "Unauthorized",
        "healing_action": "safe_abstain",
        "recoverable": False,
        "unrecoverable_reason": "missing_or_invalid_credential_material",
        "reward": 0.3,
        "reward_breakdown": {"safe_abstention_bonus": 0.3, "final_reward": 0.3},
        "retries_used": 0,
        "success": False,
        "final_status_code": 401,
    }

    transition = episode_to_rl_transition(episode)

    assert set(transition.keys()) == {"observation", "action", "reward", "done", "info"}
    assert transition["observation"]["scenario_type"] == "auth_drift"
    assert transition["action"]["repair_type"] == "safe_abstain"
    assert transition["action"]["safe_abstain"] is True
    assert transition["reward"] == 0.3
    assert transition["done"] is True
    assert transition["info"]["recoverable"] is False
