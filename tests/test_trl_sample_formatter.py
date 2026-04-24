import json

from scripts.generate_training_episodes import generate_training_episodes
from sprint4.training.trl_sample_formatter import format_trl_dataset, load_jsonl


def test_trl_sample_formatter_writes_prompt_dataset(tmp_path) -> None:
    episodes_path = tmp_path / "episodes.jsonl"
    generate_training_episodes(
        episodes=4,
        output_path=str(episodes_path),
        include_repairable=True,
        include_unrecoverable=True,
        backend="simulated",
        env_mode="local",
        cache_mode="disable",
        seed=11,
    )

    summary = format_trl_dataset(
        episodes_path=str(episodes_path),
        output_dir=str(tmp_path / "trl_dataset"),
        eval_ratio=0.25,
        seed=11,
    )

    assert summary["sample_count"] == 4
    train_rows = load_jsonl(str(tmp_path / "trl_dataset" / "train_prompts.jsonl"))
    assert train_rows
    row = train_rows[0]
    assert "strict JSON only" in row["prompt"]
    assert "failed_request=" in row["prompt"]
    target = json.loads(row["target_json"])
    assert "action" in target
    assert "safe_abstain" in target
