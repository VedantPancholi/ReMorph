"""Colab-friendly script for the larger ReMorph HF TRL training pipeline."""

from __future__ import annotations

import textwrap


def main() -> None:
    print(
        textwrap.dedent(
            """
            # ReMorph HF TRL Large Training

            ## 1. Install dependencies
            !python -m pip install -r requirements/dev.txt
            !python -m pip install -r requirements/training.txt

            ## 2. Generate or load many benchmark episodes
            !python scripts/generate_training_episodes.py \\
              --episodes 1000 \\
              --output runtime/training_large/episodes.jsonl \\
              --cache-mode disable \\
              --include-repairable \\
              --include-unrecoverable \\
              --seed 42 \\
              --backend simulated \\
              --env-mode local

            ## 3. Format the TRL dataset
            !python -m sprint4.training.trl_sample_formatter \\
              --episodes-path runtime/training_large/episodes.jsonl \\
              --output-dir runtime/training_large/trl_dataset \\
              --eval-ratio 0.2 \\
              --seed 42

            ## 4. Run HF TRL-compatible training
            !python -m sprint4.training.trl_train_grpo \\
              --train-path runtime/training_large/trl_dataset/train_prompts.jsonl \\
              --eval-path runtime/training_large/trl_dataset/eval_prompts.jsonl \\
              --output-dir runtime/training_large/trl_training \\
              --model-name sshleifer/tiny-gpt2 \\
              --max-steps 50 \\
              --batch-size 2 \\
              --learning-rate 5e-5

            ## 5. Evaluate the trained policy
            !python -m sprint4.evaluation.evaluate_trained_policy \\
              --eval-path runtime/training_large/trl_dataset/eval_prompts.jsonl \\
              --output-dir runtime/training_large/trl_training \\
              --model-path runtime/training_large/trl_training/trained_policy_model.json

            ## 6. Compare baseline vs adaptive vs trained
            !python -m sprint4.evaluation.compare_trained_vs_untrained \\
              --input-dir runtime/training_large/trl_dataset \\
              --output-dir runtime/training_large/comparison \\
              --trained-policy-summary-path runtime/training_large/trl_training/trained_policy_summary.json

            ## 7. Print the final scoreboard
            !cat runtime/training_large/comparison/comparison.md
            !cat runtime/training_large/trl_training/trained_policy_eval.md
            """
        ).strip()
    )


if __name__ == "__main__":
    main()
