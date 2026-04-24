from sprint4.training.manifests import build_experiment_manifests


def _supervised(
    episode_id: str,
    raw_scenario_type: str,
    benchmark_partition: str,
    source_name: str = "phase1",
) -> dict:
    return {
        "episode_id": episode_id,
        "raw_scenario_type": raw_scenario_type,
        "benchmark_partition": benchmark_partition,
        "provenance": {
            "source_name": source_name,
            "source_record_id": episode_id,
        },
    }


def _transition(
    episode_id: str,
    raw_scenario_type: str,
    benchmark_partition: str,
    source_name: str = "benchmark_episode",
) -> dict:
    return {
        "episode_id": episode_id,
        "raw_scenario_type": raw_scenario_type,
        "benchmark_partition": benchmark_partition,
        "provenance": {
            "source_name": source_name,
            "source_record_id": episode_id,
        },
        "outcome": {
            "request_succeeded": True,
            "http_status": 200,
            "retry_count": 0,
        },
    }


def test_manifests_stamp_contract_version_and_counts() -> None:
    manifests = build_experiment_manifests(
        supervised_rows=[
            _supervised("ep-1", "schema_missing_key", "repairable"),
            _supervised("ep-2", "auth_missing_token", "unrecoverable"),
        ],
        transition_rows=[
            _transition("ep-1", "schema_missing_key", "repairable"),
            _transition("ep-2", "auth_missing_token", "unrecoverable"),
        ],
        split_seed=7,
        eval_ratio=0.5,
    )

    assert manifests["supervised_train"]["contract_version"] == "v1"
    assert manifests["transition_train"]["contract_version"] == "v1"
    assert manifests["shared_eval"]["contract_version"] == "v1"
    assert manifests["shared_eval"]["counts_by_scenario"]


def test_shared_eval_manifest_is_stable_for_same_seed() -> None:
    inputs = dict(
        supervised_rows=[
            _supervised("ep-1", "schema_missing_key", "repairable"),
            _supervised("ep-2", "route_regression", "repairable"),
            _supervised("ep-3", "auth_missing_token", "unrecoverable"),
            _supervised("ep-4", "auth_missing_token", "unrecoverable"),
        ],
        transition_rows=[
            _transition("ep-1", "schema_missing_key", "repairable"),
            _transition("ep-2", "route_regression", "repairable"),
            _transition("ep-3", "auth_missing_token", "unrecoverable"),
            _transition("ep-4", "auth_missing_token", "unrecoverable"),
        ],
        split_seed=13,
        eval_ratio=0.5,
    )
    left = build_experiment_manifests(**inputs)
    right = build_experiment_manifests(**inputs)

    assert left["shared_eval"]["manifest_id"] == right["shared_eval"]["manifest_id"]
    assert left["shared_eval"]["supervised_row_descriptors"] == right["shared_eval"]["supervised_row_descriptors"]
    assert left["shared_eval"]["transition_row_descriptors"] == right["shared_eval"]["transition_row_descriptors"]


def test_shared_eval_manifest_changes_with_different_seed() -> None:
    kwargs = dict(
        supervised_rows=[
            _supervised("ep-1", "schema_missing_key", "repairable"),
            _supervised("ep-2", "schema_missing_key", "repairable"),
            _supervised("ep-3", "auth_missing_token", "unrecoverable"),
            _supervised("ep-4", "auth_missing_token", "unrecoverable"),
        ],
        transition_rows=[
            _transition("ep-1", "schema_missing_key", "repairable"),
            _transition("ep-2", "schema_missing_key", "repairable"),
            _transition("ep-3", "auth_missing_token", "unrecoverable"),
            _transition("ep-4", "auth_missing_token", "unrecoverable"),
        ],
        eval_ratio=0.5,
    )
    left = build_experiment_manifests(split_seed=1, **kwargs)
    right = build_experiment_manifests(split_seed=2, **kwargs)

    assert left["shared_eval"]["manifest_id"] != right["shared_eval"]["manifest_id"]


def test_manifest_reuses_shared_eval_without_policy_specific_subset() -> None:
    manifests = build_experiment_manifests(
        supervised_rows=[
            _supervised("ep-1", "schema_missing_key", "repairable"),
            _supervised("ep-2", "auth_missing_token", "unrecoverable"),
        ],
        transition_rows=[
            _transition("ep-1", "schema_missing_key", "repairable"),
            _transition("ep-2", "auth_missing_token", "unrecoverable"),
        ],
        split_seed=7,
        eval_ratio=0.5,
    )

    assert "supervised_row_descriptors" in manifests["shared_eval"]
    assert "transition_row_descriptors" in manifests["shared_eval"]
    assert "policy_name" not in manifests["shared_eval"]
