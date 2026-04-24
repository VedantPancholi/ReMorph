from sprint4.training.split_strategy import build_group_id, split_rows_grouped


def _row(
    episode_id: str,
    raw_scenario_type: str,
    benchmark_partition: str,
    source_name: str = "benchmark_episode",
    source_record_id: str | None = None,
) -> dict:
    return {
        "episode_id": episode_id,
        "raw_scenario_type": raw_scenario_type,
        "benchmark_partition": benchmark_partition,
        "provenance": {
            "source_name": source_name,
            "source_record_id": source_record_id or episode_id,
        },
    }


def test_split_strategy_is_deterministic_for_same_seed() -> None:
    rows = [
        _row("ep-1", "schema_missing_key", "repairable"),
        _row("ep-2", "schema_missing_key", "repairable"),
        _row("ep-3", "auth_missing_token", "unrecoverable"),
        _row("ep-4", "auth_missing_token", "unrecoverable"),
    ]
    split_a = split_rows_grouped(rows, eval_ratio=0.5, seed=7)
    split_b = split_rows_grouped(rows, eval_ratio=0.5, seed=7)

    assert [row["episode_id"] for row in split_a[1]] == [row["episode_id"] for row in split_b[1]]
    assert split_a[2] == split_b[2]


def test_split_strategy_changes_with_different_seed() -> None:
    rows = [
        _row("ep-1", "schema_missing_key", "repairable"),
        _row("ep-2", "schema_missing_key", "repairable"),
        _row("ep-3", "schema_missing_key", "repairable"),
        _row("ep-4", "auth_missing_token", "unrecoverable"),
        _row("ep-5", "auth_missing_token", "unrecoverable"),
        _row("ep-6", "auth_missing_token", "unrecoverable"),
    ]
    split_a = split_rows_grouped(rows, eval_ratio=0.5, seed=7)
    split_b = split_rows_grouped(rows, eval_ratio=0.5, seed=99)

    assert split_a[2] != split_b[2]


def test_split_strategy_preserves_scenario_and_partition_strata() -> None:
    rows = [
        _row("ep-1", "schema_missing_key", "repairable"),
        _row("ep-2", "schema_missing_key", "repairable"),
        _row("ep-3", "route_regression", "repairable"),
        _row("ep-4", "route_regression", "repairable"),
        _row("ep-5", "auth_missing_token", "unrecoverable"),
        _row("ep-6", "auth_missing_token", "unrecoverable"),
    ]
    train_rows, eval_rows, _assignments = split_rows_grouped(rows, eval_ratio=0.5, seed=11)

    eval_scenarios = {row["raw_scenario_type"] for row in eval_rows}
    eval_partitions = {row["benchmark_partition"] for row in eval_rows}
    assert {"schema_missing_key", "route_regression", "auth_missing_token"} <= eval_scenarios
    assert {"repairable", "unrecoverable"} <= eval_partitions
    assert len(train_rows) + len(eval_rows) == len(rows)


def test_split_strategy_prevents_leakage_across_grouped_rows() -> None:
    rows = [
        _row("ep-1", "schema_missing_key", "repairable", source_record_id="shared-1"),
        _row("ep-1", "schema_missing_key", "repairable", source_record_id="shared-1"),
        _row("ep-2", "schema_missing_key", "repairable", source_record_id="shared-2"),
        _row("ep-3", "schema_missing_key", "repairable", source_record_id="shared-3"),
    ]
    train_rows, eval_rows, _assignments = split_rows_grouped(rows, eval_ratio=0.5, seed=5)

    train_groups = {build_group_id(row) for row in train_rows}
    eval_groups = {build_group_id(row) for row in eval_rows}
    assert train_groups.isdisjoint(eval_groups)


def test_group_id_aligns_same_scenario_across_policies() -> None:
    baseline_row = {
        "episode_id": "baseline-only-id",
        "raw_scenario_type": "route_regression",
        "benchmark_partition": "repairable",
        "state": {
            "scenario_type": "route_drift",
            "raw_scenario_type": "route_regression",
            "benchmark_partition": "repairable",
            "request_method": "POST",
            "request_path": "/api/v0/payments/process",
            "request_query": {"tenant": "a"},
            "request_body": {"amount": 100},
        },
        "provenance": {
            "source_name": "benchmark_episode",
            "source_record_id": "baseline-only-id",
        },
    }
    adaptive_row = {
        "episode_id": "adaptive-random-id",
        "raw_scenario_type": "route_regression",
        "benchmark_partition": "repairable",
        "state": {
            "scenario_type": "route_drift",
            "raw_scenario_type": "route_regression",
            "benchmark_partition": "repairable",
            "request_method": "POST",
            "request_path": "/api/v0/payments/process",
            "request_query": {"tenant": "a"},
            "request_body": {"amount": 100},
        },
        "provenance": {
            "source_name": "benchmark_episode",
            "source_record_id": "adaptive-random-id",
        },
    }

    assert build_group_id(baseline_row) == build_group_id(adaptive_row)
