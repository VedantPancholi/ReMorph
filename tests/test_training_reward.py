from sprint4.training.training_reward import score_training_decision


def test_training_reward_rewards_correct_repair_action() -> None:
    reference = {
        "recoverable": True,
        "target_action": {
            "action": "route_rewrite",
            "selected_endpoint": "/api/v2/finance/ledger",
            "method_rewrite": False,
            "payload_rewrite": False,
            "auth_rewrite": True,
            "safe_abstain": False,
        },
    }

    result = score_training_decision(
        {
            "action": "route_rewrite",
            "selected_endpoint": "/api/v2/finance/ledger",
            "method_rewrite": False,
            "payload_rewrite": False,
            "auth_rewrite": True,
            "safe_abstain": False,
        },
        reference,
    )

    assert result.total_reward > 1.0
    assert result.reward_breakdown["correct_action_reward"] == 1.0
    assert result.reward_breakdown["selected_endpoint_reward"] == 0.5


def test_training_reward_rewards_safe_abstention() -> None:
    reference = {
        "recoverable": False,
        "target_action": {
            "action": "safe_abstain",
            "selected_endpoint": None,
            "method_rewrite": False,
            "payload_rewrite": False,
            "auth_rewrite": False,
            "safe_abstain": True,
            "unrecoverable_reason": "missing_or_invalid_credential_material",
        },
    }

    result = score_training_decision(
        {
            "action": "safe_abstain",
            "selected_endpoint": None,
            "method_rewrite": False,
            "payload_rewrite": False,
            "auth_rewrite": False,
            "safe_abstain": True,
            "unrecoverable_reason": "missing_or_invalid_credential_material",
        },
        reference,
    )

    assert result.total_reward == 0.5
    assert result.reward_breakdown["safe_abstain_reward"] == 0.5


def test_training_reward_penalizes_hallucinated_repair_on_unrecoverable() -> None:
    reference = {
        "recoverable": False,
        "target_action": {
            "action": "safe_abstain",
            "selected_endpoint": None,
            "method_rewrite": False,
            "payload_rewrite": False,
            "auth_rewrite": False,
            "safe_abstain": True,
            "unrecoverable_reason": "missing_or_invalid_credential_material",
        },
    }

    result = score_training_decision(
        {
            "action": "auth_rewrite",
            "selected_endpoint": "/api/v2/finance/ledger",
            "method_rewrite": False,
            "payload_rewrite": False,
            "auth_rewrite": True,
            "safe_abstain": False,
        },
        reference,
    )

    assert result.total_reward < 0.0
    assert result.reward_breakdown["hallucinated_repair_penalty"] == -0.7
