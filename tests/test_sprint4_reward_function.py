from sprint4.rewards.reward_function import RewardFunction, RewardSignals


def test_reward_function_returns_configured_breakdown() -> None:
    reward_function = RewardFunction()
    result = reward_function.score(
        RewardSignals(
            repaired_success=True,
            fixed_in_one_cycle=False,
            extra_retries=2,
            hallucinated_fields=True,
            wrong_route_candidate=False,
            final_recovery_failed=False,
        )
    )
    assert result.total_reward == 0.3
    assert result.breakdown["success_reward"] == 1.0
    assert result.breakdown["retry_penalty"] == -0.2
    assert result.breakdown["hallucination_penalty"] == -0.5
    assert result.breakdown["final_reward"] == 0.3
    assert result.breakdown["success_bonus"] == 1.0


def test_reward_function_rewards_safe_abstention_better_than_hallucinated_repair() -> None:
    reward_function = RewardFunction()

    safe_abstain = reward_function.score(
        RewardSignals(
            repaired_success=False,
            fixed_in_one_cycle=False,
            extra_retries=0,
            hallucinated_fields=False,
            wrong_route_candidate=False,
            final_recovery_failed=False,
            safe_abstained=True,
            unrecoverable=True,
        )
    )
    hallucinated_repair = reward_function.score(
        RewardSignals(
            repaired_success=False,
            fixed_in_one_cycle=False,
            extra_retries=1,
            hallucinated_fields=False,
            wrong_route_candidate=False,
            final_recovery_failed=True,
            unrecoverable=True,
            unsafe_hallucinated_repair=True,
        )
    )

    assert safe_abstain.breakdown["safe_abstention_bonus"] > 0.0
    assert hallucinated_repair.breakdown["hallucination_penalty"] < 0.0
    assert hallucinated_repair.breakdown["unrecoverable_penalty"] < 0.0
    assert safe_abstain.total_reward > hallucinated_repair.total_reward
