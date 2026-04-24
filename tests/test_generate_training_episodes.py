import json

from scripts.generate_training_episodes import generate_training_episodes


def test_generate_training_episodes_writes_records_and_summary(tmp_path) -> None:
    output_path = tmp_path / "episodes.jsonl"

    summary = generate_training_episodes(
        episodes=6,
        output_path=str(output_path),
        cache_mode="disable",
        include_repairable=True,
        include_unrecoverable=True,
        seed=7,
        backend="simulated",
        env_mode="local",
    )

    assert output_path.exists()
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 6
    first = json.loads(lines[0])
    assert first["agent_type"] == "adaptive"
    assert "raw_scenario_type" in first
    assert "reward_breakdown" in first

    assert summary["total_episodes"] == 6
    assert summary["repairable_count"] + summary["unrecoverable_count"] == 6
    assert "scenario_distribution" in summary
    assert "safe_abstention_count" in summary
