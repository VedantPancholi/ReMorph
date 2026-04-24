import json
import sys
from types import SimpleNamespace

from sprint4.evaluation.evaluate_trained_policy import evaluate_trained_policy
from sprint4.training.trl_sample_formatter import format_trl_dataset
from sprint4.training.trl_train_grpo import run_trl_training
from scripts.generate_training_episodes import generate_training_episodes


def test_evaluate_trained_policy_writes_report_shape(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "trl", SimpleNamespace(__version__="0.test"))

    episodes_path = tmp_path / "episodes.jsonl"
    generate_training_episodes(
        episodes=6,
        output_path=str(episodes_path),
        include_repairable=True,
        include_unrecoverable=True,
        backend="simulated",
        env_mode="local",
        cache_mode="disable",
        seed=5,
    )
    format_trl_dataset(
        episodes_path=str(episodes_path),
        output_dir=str(tmp_path / "trl_dataset"),
        eval_ratio=0.34,
        seed=5,
    )
    run_trl_training(
        train_path=str(tmp_path / "trl_dataset" / "train_prompts.jsonl"),
        eval_path=str(tmp_path / "trl_dataset" / "eval_prompts.jsonl"),
        output_dir=str(tmp_path / "trl_training"),
        max_steps=4,
    )

    report = evaluate_trained_policy(
        eval_path=str(tmp_path / "trl_dataset" / "eval_prompts.jsonl"),
        output_dir=str(tmp_path / "trained_eval"),
        model_path=str(tmp_path / "trl_training" / "trained_policy_model.json"),
    )

    assert (tmp_path / "trained_eval" / "trained_policy_eval.json").exists()
    assert (tmp_path / "trained_eval" / "trained_policy_eval.md").exists()
    trained = report["policies"]["trained_policy"]
    assert trained["status"] == "completed"
    assert "correct_action_rate" in trained
    assert "hallucination_on_unrecoverable_rate" in trained
