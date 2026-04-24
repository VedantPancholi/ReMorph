"""TRL GRPO training entrypoint with optional real trainer execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sprint4.training.episode_dataset import (
    generate_training_dataset,
    summarize_samples,
)
from sprint4.training.policy_adapter import build_policy_batch


def run_trl_training(
    *,
    episodes_path: str,
    output_dir: str,
    eval_ratio: float = 0.2,
    seed: int = 42,
    model_name: str | None = None,
    train_model: bool | None = None,
    max_steps: int = 1,
    per_device_train_batch_size: int = 1,
    gradient_accumulation_steps: int = 1,
    learning_rate: float = 1e-6,
    num_generations: int = 2,
    max_completion_length: int = 128,
) -> dict[str, object]:
    """Prepare TRL-ready artifacts and optionally run a small GRPO training loop."""
    try:
        import trl  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "TRL is not installed. Install optional dependencies before running training."
        ) from exc

    dataset_manifest = generate_training_dataset(
        episodes_path=episodes_path,
        output_dir=output_dir,
        agent_type="adaptive",
        include_failed=False,
        eval_ratio=eval_ratio,
        seed=seed,
    )
    train_rows = _load_dataset_rows(dataset_manifest["train_path"])
    eval_rows = _load_dataset_rows(dataset_manifest["eval_path"])
    batch = build_policy_batch(train_rows)
    eval_summary = summarize_samples(eval_rows)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    should_train = bool(model_name) if train_model is None else bool(train_model)
    if should_train and not model_name:
        raise ValueError("model_name is required when train_model is enabled")

    training_summary: dict[str, object]
    if should_train:
        training_summary = _run_grpo_training(
            model_name=str(model_name),
            train_rows=train_rows,
            eval_rows=eval_rows,
            output_dir=output,
            seed=seed,
            max_steps=max_steps,
            per_device_train_batch_size=per_device_train_batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            learning_rate=learning_rate,
            num_generations=num_generations,
            max_completion_length=max_completion_length,
        )
        note = "Prepared TRL-ready datasets and executed a lightweight GRPO training loop."
    else:
        training_summary = {
            "status": "not_run",
            "reason": "No model_name was provided, so only TRL-ready dataset artifacts were prepared.",
        }
        note = "Prepared TRL-ready prompt/completion datasets and offline eval summary."

    summary = {
        "trainer": "trl_grpo",
        "trl_version": getattr(trl, "__version__", "unknown"),
        "sample_count": dataset_manifest["sample_count"],
        "train_sample_count": dataset_manifest["train_sample_count"],
        "eval_sample_count": dataset_manifest["eval_sample_count"],
        "avg_reward": round(sum(batch.rewards) / max(1, len(batch.rewards)), 4),
        "dataset_artifacts": dataset_manifest,
        "eval_summary": eval_summary,
        "training": training_summary,
        "note": note,
    }
    (output / "trl_training_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def _run_grpo_training(
    *,
    model_name: str,
    train_rows: list[dict[str, object]],
    eval_rows: list[dict[str, object]],
    output_dir: Path,
    seed: int,
    max_steps: int,
    per_device_train_batch_size: int,
    gradient_accumulation_steps: int,
    learning_rate: float,
    num_generations: int,
    max_completion_length: int,
) -> dict[str, object]:
    if not train_rows:
        return {
            "status": "skipped",
            "reason": "No train rows were available for GRPO training.",
        }

    GRPOConfig, GRPOTrainer = _import_trl_grpo_components()
    Dataset, AutoTokenizer, torch = _import_training_stack()

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if getattr(tokenizer, "pad_token_id", None) is None:
        eos_token = getattr(tokenizer, "eos_token", None)
        if eos_token is not None:
            tokenizer.pad_token = eos_token

    trainer_output_dir = output_dir / "grpo_run"
    trainer_output_dir.mkdir(parents=True, exist_ok=True)
    model_output_dir = output_dir / "grpo_model"

    train_dataset = Dataset.from_list([_to_trl_training_row(row) for row in train_rows])
    eval_dataset = Dataset.from_list([_to_trl_training_row(row) for row in eval_rows]) if eval_rows else None

    training_args = GRPOConfig(
        output_dir=str(trainer_output_dir),
        run_name="sprint4_grpo_demo",
        do_train=True,
        do_eval=bool(eval_rows),
        eval_strategy="steps" if eval_rows else "no",
        eval_steps=1 if eval_rows else None,
        per_device_train_batch_size=max(1, int(per_device_train_batch_size)),
        gradient_accumulation_steps=max(1, int(gradient_accumulation_steps)),
        learning_rate=float(learning_rate),
        max_steps=max(1, int(max_steps)),
        num_generations=max(1, int(num_generations)),
        max_completion_length=max(16, int(max_completion_length)),
        logging_steps=1,
        save_strategy="no",
        report_to="none",
        remove_unused_columns=False,
        seed=int(seed),
        use_cpu=not bool(getattr(torch.cuda, "is_available", lambda: False)()),
    )

    trainer = GRPOTrainer(
        model=model_name,
        reward_funcs=_json_completion_reward,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
    )
    train_result = trainer.train()
    trainer.save_model(str(model_output_dir))
    if hasattr(tokenizer, "save_pretrained"):
        tokenizer.save_pretrained(str(model_output_dir))

    metrics = dict(getattr(train_result, "metrics", {}) or {})
    training_summary = {
        "status": "completed",
        "model_name": model_name,
        "trainer_output_dir": str(trainer_output_dir),
        "model_output_dir": str(model_output_dir),
        "train_row_count": len(train_rows),
        "eval_row_count": len(eval_rows),
        "global_step": getattr(getattr(trainer, "state", None), "global_step", None),
        "metrics": metrics,
        "reward_function": "json_completion_reward",
        "config": {
            "max_steps": max(1, int(max_steps)),
            "per_device_train_batch_size": max(1, int(per_device_train_batch_size)),
            "gradient_accumulation_steps": max(1, int(gradient_accumulation_steps)),
            "learning_rate": float(learning_rate),
            "num_generations": max(1, int(num_generations)),
            "max_completion_length": max(16, int(max_completion_length)),
            "seed": int(seed),
        },
    }
    (output_dir / "trl_grpo_run_summary.json").write_text(
        json.dumps(training_summary, indent=2),
        encoding="utf-8",
    )
    return training_summary


def _import_trl_grpo_components():
    from pathlib import Path as _Path

    original_read_text = _Path.read_text

    def _utf8_read_text(self, *args, **kwargs):
        if "encoding" not in kwargs and not args:
            kwargs["encoding"] = "utf-8"
        return original_read_text(self, *args, **kwargs)

    _Path.read_text = _utf8_read_text
    try:
        from trl import GRPOConfig, GRPOTrainer  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "TRL GRPO components could not be imported. On Windows, verify the environment uses UTF-8 mode."
        ) from exc
    finally:
        _Path.read_text = original_read_text
    return GRPOConfig, GRPOTrainer


def _import_training_stack():
    try:
        from datasets import Dataset  # type: ignore
        import torch  # type: ignore
        from transformers import AutoTokenizer  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Training dependencies are incomplete. Install datasets, transformers, accelerate, and torch."
        ) from exc
    return Dataset, AutoTokenizer, torch


def _to_trl_training_row(row: dict[str, object]) -> dict[str, object]:
    metadata = row.get("metadata")
    metadata_dict = metadata if isinstance(metadata, dict) else {}
    action = row.get("action")
    action_dict = action if isinstance(action, dict) else {}
    return {
        "prompt": str(row.get("prompt") or ""),
        "target_completion": str(row.get("completion") or ""),
        "reference_reward": float(row.get("reward") or 0.0),
        "scenario_type": row.get("scenario_type"),
        "raw_scenario_type": row.get("raw_scenario_type"),
        "benchmark_partition": metadata_dict.get("benchmark_partition"),
        "target_action_type": action_dict.get("action_type"),
    }


def _json_completion_reward(
    *,
    completions: list[Any],
    target_completion: list[str],
    reference_reward: list[float],
    **_: Any,
) -> list[float]:
    rewards: list[float] = []
    for completion, target, ref_reward in zip(
        completions,
        target_completion,
        reference_reward,
        strict=True,
    ):
        rewards.append(
            _score_generated_completion(
                generated_text=_completion_to_text(completion),
                target_text=target,
                reference_reward=float(ref_reward),
            )
        )
    return rewards


def _score_generated_completion(
    *,
    generated_text: str,
    target_text: str,
    reference_reward: float,
) -> float:
    target_action = _try_load_json_object(target_text)
    generated_action = _try_load_json_object(generated_text)

    if target_action is None:
        return 0.0
    if generated_action is None:
        return -0.25
    if generated_action == target_action:
        return 1.0

    score = 0.0
    if generated_action.get("action_type") == target_action.get("action_type"):
        score += 0.4
    score += _field_match_score(generated_action, target_action, "target_method", 0.15)
    score += _field_match_score(generated_action, target_action, "target_path", 0.15)
    score += _field_match_score(generated_action, target_action, "header_patch", 0.1)
    score += _field_match_score(generated_action, target_action, "body_patch", 0.1)
    score += _field_match_score(generated_action, target_action, "query_patch", 0.1)
    if generated_action.get("reason"):
        score += 0.05

    # Keep the reward mildly shaped around the original successful example reward.
    score += min(max(reference_reward, 0.0), 2.0) * 0.025
    return round(max(-0.25, min(score, 1.0)), 4)


def _field_match_score(
    generated_action: dict[str, Any],
    target_action: dict[str, Any],
    field_name: str,
    weight: float,
) -> float:
    if field_name not in target_action:
        return 0.0
    return weight if generated_action.get(field_name) == target_action.get(field_name) else 0.0


def _completion_to_text(completion: Any) -> str:
    if isinstance(completion, str):
        return completion.strip()
    if isinstance(completion, dict):
        content = completion.get("content")
        return str(content).strip() if content is not None else json.dumps(completion, sort_keys=True)
    if isinstance(completion, list):
        text_chunks: list[str] = []
        for item in completion:
            if isinstance(item, str):
                text_chunks.append(item)
            elif isinstance(item, dict) and item.get("content") is not None:
                text_chunks.append(str(item.get("content")))
            else:
                text_chunks.append(json.dumps(item, sort_keys=True))
        return "\n".join(chunk.strip() for chunk in text_chunks if chunk).strip()
    return str(completion).strip()


def _try_load_json_object(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    if not candidate:
        return None
    parsed = _try_json_load(candidate)
    if isinstance(parsed, dict):
        return parsed

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    parsed = _try_json_load(candidate[start : end + 1])
    return parsed if isinstance(parsed, dict) else None


def _try_json_load(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _load_dataset_rows(path: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    file_path = Path(path)
    if not file_path.exists():
        return rows
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run lightweight TRL GRPO demo flow.")
    parser.add_argument(
        "--episodes-path",
        default="runtime/sprint4/episodes.jsonl",
        help="Input Sprint 4 episode JSONL file.",
    )
    parser.add_argument(
        "--output-dir",
        default="runtime/sprint4/training",
        help="Directory to store training artifacts.",
    )
    parser.add_argument("--eval-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--model-name",
        default="",
        help="Optional Hugging Face model name or local model path for real GRPO training.",
    )
    parser.add_argument(
        "--train-model",
        action="store_true",
        help="Run a lightweight GRPO training loop after dataset preparation.",
    )
    parser.add_argument("--max-steps", type=int, default=1)
    parser.add_argument("--per-device-train-batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=1e-6)
    parser.add_argument("--num-generations", type=int, default=2)
    parser.add_argument("--max-completion-length", type=int, default=128)
    args = parser.parse_args()
    summary = run_trl_training(
        episodes_path=args.episodes_path,
        output_dir=args.output_dir,
        eval_ratio=args.eval_ratio,
        seed=args.seed,
        model_name=args.model_name or None,
        train_model=bool(args.train_model),
        max_steps=args.max_steps,
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        num_generations=args.num_generations,
        max_completion_length=args.max_completion_length,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
