# RL-Facing Layer

This layer sits on top of the existing Sprint 4 runtime without replacing the Sprint 2 repair brain, the benchmark runner, or the OpenEnv adapter.

## Flow

1. `sprint4/env/openenv_adapter.py`
   Normalizes an OpenEnv-style client into the existing `APIEnvironment` contract.

2. `sprint4/proxy/workflow_runner.py`
   Executes the failed request, captures the trapped error, applies repair logic when the scenario is recoverable, and records explicit `safe_abstain` outcomes for unrecoverable auth failures such as `auth_missing_token` and `auth_malformed_jwt`.

3. `sprint4/rewards/reward_function.py`
   Produces a deterministic reward breakdown with:
   - `success_reward`
   - `one_cycle_bonus`
   - `retry_penalty`
   - `wrong_route_penalty`
   - `hallucination_penalty`
   - `safe_abstention_bonus`
   - `unrecoverable_penalty`
   - `final_reward`

4. `sprint4/training/policy_adapter.py`
   Converts episode records or OpenEnv-like step results into an RL-facing transition:
   - `observation`
   - `action`
   - `reward`
   - `done`
   - `info`

5. `sprint4/training/episode_dataset.py`
   Reads runtime `episodes.jsonl`, normalizes each row through the policy adapter, filters repairable or unrecoverable slices, and writes:
   - `train.jsonl`
   - `eval.jsonl`
   - `dataset_summary.json`

6. Optional TRL / policy training
   Training remains optional. The RL-facing dataset is designed so TRL or another policy learner can consume the exported transitions without making training dependencies mandatory for normal tests.

7. Large prompt-based training path
   `sprint4/training/trl_sample_formatter.py` can convert benchmark episodes into
   compact prompt and strict-JSON target rows for the larger policy-learning
   pipeline.

## Current Status

This layer is now implemented end to end in the repo:

- reward breakdown is emitted in episode traces
- unrecoverable auth produces `safe_abstain`
- RL-facing train and eval datasets are exported from `episodes.jsonl`
- baseline vs adaptive vs trained-policy-placeholder comparison reports are generated
- clean benchmark evidence is packaged under `runtime/sprint4_final_clean/package/`
- a larger generated training run exists under `runtime/training_large/`
- reward-curve, trained-policy summary, and trained-policy evaluation artifacts
  are now produced for the larger prompt-based pipeline

The clean package demonstrates both:

- repairable drift, where adaptive repair beats baseline
- unrecoverable auth, where adaptive abstains safely instead of inventing credentials

The larger training run currently demonstrates:

- `1000` generated episodes
- `800` repairable cases
- `200` unrecoverable cases
- trained policy is valid and safe, but still slightly below adaptive rules on
  average reward

## Safety Behavior

Unrecoverable auth failures are treated as hard negatives. The runtime should not invent bearer tokens or malformed JWT replacements. Instead, the episode trace records:

- `healing_action = "safe_abstain"`
- `recoverable = false`
- `unrecoverable_reason = "missing_or_invalid_credential_material"`

This lets offline training and evaluation distinguish:

- successful repair on recoverable cases
- safe abstention on unrecoverable cases
- unsafe hallucinated repair attempts

## Comparison Layer

`sprint4/evaluation/compare_trained_vs_untrained.py` compares:

- `baseline`
- `adaptive_rules`
- `trained_policy`

using shared metrics:

- `success_rate`
- `avg_reward`
- `avg_retries`
- `repairable_success_rate`
- `unrecoverable_safety_rate`
- `safe_abstention_accuracy`

For the larger training evaluator, `sprint4/evaluation/evaluate_trained_policy.py`
also reports:

- `correct_action_rate`
- `endpoint_accuracy`
- `hallucination_on_unrecoverable_rate`
- `invalid_json_rate`

## Optional Training Notes

The optional training path currently uses:

- `scripts/generate_training_episodes.py`
- `sprint4/training/trl_sample_formatter.py`
- `sprint4/training/trl_train_grpo.py`
- `sprint4/evaluation/evaluate_trained_policy.py`
- `sprint4/evaluation/reward_curve.py`

Expected outputs include:

- `episode_generation_summary.json`
- `trl_dataset_summary.json`
- `training_metrics.json`
- `reward_curve.json`
- `reward_curve.png`
- `trained_policy_summary.json`
- `trained_policy_eval.json`
- `trained_policy_eval.md`

If reward-curve export fails with `ModuleNotFoundError: matplotlib`, install the
training extras from `requirements/training.txt` and rerun the training command.

If `scripts/generate_training_episodes.py` is run directly, it now bootstraps
the repo root on `sys.path` so the `sprint4` imports resolve correctly.

## Minimal Run Sequence

1. Run a benchmark into an output directory such as `runtime/sprint4_final_clean/local/`.
2. Convert `episodes.jsonl` into RL-facing data with `sprint4.training.episode_dataset`.
3. Generate comparison reports with `sprint4.evaluation.compare_trained_vs_untrained`.
4. Optionally run `sprint4.training.trl_train_grpo` and regenerate comparison with
   `--trained-policy-summary-path`.

## Large Run Sequence

1. Generate many episodes with `scripts/generate_training_episodes.py`.
2. Format prompt and target rows with `sprint4.training.trl_sample_formatter`.
3. Run `sprint4.training.trl_train_grpo`.
4. Evaluate with `sprint4.evaluation.evaluate_trained_policy`.
5. Compare with `sprint4.evaluation.compare_trained_vs_untrained`.

Current honest takeaway:

- the pipeline is working end to end
- safe abstention is preserved
- the current learned policy does not yet beat adaptive rules on reward
