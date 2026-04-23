# Reward Design

## Deterministic Scoring
Reward is additive and fully explainable:

- `+1.0` if repaired request succeeds
- `+0.2` if fixed in one repair cycle
- `-0.1` per extra retry
- `-0.2` if hallucinated fields appear
- `-0.3` if wrong route candidate selected
- `-1.0` if final recovery fails

## Why This Shape
- Encourages successful recoveries.
- Prefers faster repairs.
- Penalizes unsafe or low-precision behavior.
- Keeps signal simple enough for hackathon iteration and lightweight GRPO demos.

