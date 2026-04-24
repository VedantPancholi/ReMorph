# Supervised Warm-Start

## Purpose

This is the first learned-policy checkpoint after freezing the repo-native
pre-training scoreboard.

The goal is not full RL yet. The goal is to train a small supervised policy on
canonical `SupervisedRow` data and evaluate it on the same frozen shared eval
manifest used for baseline and adaptive comparisons.

## Artifacts

- Training code:
  - `sprint4/training/supervised_warmstart.py`
  - `scripts/train_sprint4_supervised.py`
- Frozen pre-training protocol:
  - `artifacts/sprint4/eval/pretraining_scoreboard/`
- Warm-start outputs:
  - `artifacts/sprint4/training/supervised_warmstart/`

## Current Checkpoint

- shared eval manifest id: `c6cc003f9220869e`
- supervised train manifest id: `392da4c1bd22ba27`
- training rows: `33`
- model kind: `prototype_knn_v1`

## Current Scoreboard

| Policy | Overall Success | Repairable Success | Correct Abstain | Avg Reward | Avg Retries |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 0.30 | 0.125 | 1.00 | 0.0 | 0.0 |
| Adaptive | 1.00 | 1.00 | 1.00 | 10.7 | 0.9 |
| Warm-start | 0.50 | 0.375 | 1.00 | 0.7 | 0.9 |

## What This Means

- warm-start already improves over baseline on the frozen eval set
- adaptive still remains substantially better
- the learned policy is not hallucinating auth and keeps unrecoverable abstention behavior clean
- the remaining gap is mainly inside repairable slices

## Known Weaknesses

The warm-start checkpoint is still weak on:

- `auth_missing_tenant`
- `schema_type_coercion`
- `route_method_spoof`
- `schema_missing_key`
- `route_regression`

These are the best candidates for future refinement, whether through better
serialization, a stronger supervised model, or later reward-guided tuning.

## Error Analysis

Artifacts:

- `artifacts/sprint4/training/supervised_warmstart/error_analysis/warmstart_error_analysis.json`
- `artifacts/sprint4/training/supervised_warmstart/error_analysis/warmstart_error_analysis.md`
- `artifacts/sprint4/training/supervised_warmstart/error_analysis/missed_by_scenario.json`
- `artifacts/sprint4/training/supervised_warmstart/error_analysis/action_confusion.json`

Current findings:

- missed scenarios on the frozen eval set:
  - `route_regression`
  - `auth_missing_tenant`
  - `schema_type_coercion`
  - `route_method_spoof`
  - `schema_missing_key`
- no repairable false abstentions were observed in this checkpoint
- no unsafe auth hallucinations were observed
- the largest reward gap is `route_regression`, where the learned policy chooses
  the wrong route family at low confidence
- the main confusion is `repair_auth -> repair_payload`, which explains the
  `auth_missing_tenant` miss

Interpretation:

- the next refinement should be targeted, not architectural
- route selection and payload/auth separation are better targets than jumping
  straight into full RL

## Important Evaluation Rule

The warm-start policy must continue to use the frozen shared eval manifest.
Do not create a new eval split for convenience.

## Targeted Refinement

Artifacts:

- `sprint4/training/targeted_refinement.py`
- `scripts/refine_sprint4_warmstart.py`
- `artifacts/sprint4/training/supervised_warmstart_refined_validation3/`

What this adds:

- a deterministic refinement plan built from the warm-start error-analysis
  artifacts
- scenario-targeted weighting for the weak repairable slices
- optional top-k prototype voting on focus scenarios only
- an explicit adoption gate that refuses to promote a candidate unless it beats
  the frozen warm-start checkpoint without regressing abstention safety

Current result:

- the first real heuristic refinement candidate is **not promoted**
- recommendation remains `warmstart`
- candidate deltas vs warm-start on the frozen shared eval manifest:
  - success rate: `-0.4`
  - average reward: `-8.4`
  - correct abstention rate: `-1.0`

Interpretation:

- the refinement infrastructure is ready
- the current heuristic weighting is too blunt for promotion
- next refinement work should be more conservative and likely needs either:
  - better serialization / decoder separation
  - scenario-local augmentation
  - a stricter abstention-preserving refinement objective
