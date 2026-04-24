"""Copy-paste runnable Google Colab script for minimal ReMorph TRL training."""

# ============================================
# 1. Install dependencies
# ============================================
# !pip install trl transformers accelerate datasets torch matplotlib

# ============================================
# 2. Clone or load the repo
# ============================================
# !git clone <your-remorph-repo-url>
# %cd ReMorph

# ============================================
# 3. Run benchmark and dataset export
# ============================================
# !python scripts/run_benchmark.py \
#   --backend simulated \
#   --env-mode local \
#   --output-dir runtime/sprint4_colab/local \
#   --cache-mode clear \
#   --disable-telemetry
#
# !python -m sprint4.training.episode_dataset \
#   --episodes-path runtime/sprint4_colab/local/episodes.jsonl \
#   --output-dir runtime/sprint4_colab/training_dataset \
#   --split all

# ============================================
# 4. Run minimal TRL training
# ============================================
# !python -m sprint4.training.trl_train_grpo \
#   --train-path runtime/sprint4_colab/training_dataset/train.jsonl \
#   --eval-path runtime/sprint4_colab/training_dataset/eval.jsonl \
#   --output-dir runtime/sprint4_colab/trl_training \
#   --model-name sshleifer/tiny-gpt2

# ============================================
# 5. Plot reward curve
# ============================================
# !python -m sprint4.evaluation.reward_curve \
#   --metrics-path runtime/sprint4_colab/trl_training/training_metrics.json \
#   --output-dir runtime/sprint4_colab/trl_training

# ============================================
# 6. Run trained-vs-untrained comparison
# ============================================
# !python -m sprint4.evaluation.compare_trained_vs_untrained \
#   --input-dir runtime/sprint4_colab/training_dataset \
#   --output-dir runtime/sprint4_colab/comparison \
#   --trained-policy-summary-path runtime/sprint4_colab/trl_training/trained_policy_summary.json

# ============================================
# 7. Inspect artifacts
# ============================================
# !cat runtime/sprint4_colab/trl_training/trained_policy_summary.json
# !cat runtime/sprint4_colab/comparison/comparison.md

print(
    "This file is meant to be copied into Google Colab cells. "
    "Uncomment the commands section by section to run the full ReMorph demo."
)
