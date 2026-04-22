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
    assert result.total_reward == 0.6
    assert result.breakdown["success_bonus"] == 1.0
    assert result.breakdown["extra_retry_penalty"] == -0.2
    assert result.breakdown["hallucinated_fields_penalty"] == -0.2

