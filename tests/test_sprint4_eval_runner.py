import json

from sprint4.eval.eval_runner import persist_comparison, run_eval


def _transition_row(
    *,
    episode_id: str,
    raw_scenario_type: str,
    benchmark_partition: str,
    success: bool,
    outcome_class: str,
    reward_total: float,
) -> dict:
    return {
        "episode_id": episode_id,
        "state": {
            "scenario_type": "route_drift" if benchmark_partition == "repairable" else "auth_drift",
            "contract_version": "v1",
            "benchmark_partition": benchmark_partition,
            "raw_scenario_type": raw_scenario_type,
        },
        "outcome": {
            "request_succeeded": success,
            "http_status": 200 if success else 401,
            "retry_count": 0,
            "selected_route_correct": True,
            "used_hallucinated_auth": False,
        },
        "reward_breakdown": {"reward_total": reward_total},
        "success": success,
        "outcome_class": outcome_class,
        "raw_scenario_type": raw_scenario_type,
        "benchmark_partition": benchmark_partition,
        "contract_version": "v1",
        "provenance": {
            "source_name": "benchmark_episode",
            "source_record_id": episode_id,
        },
    }


def test_eval_runner_persists_run_outputs(tmp_path) -> None:
    manifest = {
        "manifest_id": "shared-1",
        "transition_row_descriptors": [
            {"group_id": "ep-1"},
            {"group_id": "ep-2"},
        ],
    }
    rows = [
        _transition_row(
            episode_id="ep-1",
            raw_scenario_type="route_regression",
            benchmark_partition="repairable",
            success=True,
            outcome_class="repair_success",
            reward_total=15.0,
        ),
        _transition_row(
            episode_id="ep-2",
            raw_scenario_type="auth_missing_token",
            benchmark_partition="unrecoverable",
            success=True,
            outcome_class="correct_abstain",
            reward_total=8.0,
        ),
    ]

    result = run_eval(
        policy_name="adaptive",
        manifest=manifest,
        transition_rows=rows,
        output_dir=str(tmp_path / "adaptive"),
    )

    assert result["manifest_id"] == "shared-1"
    assert len(result["eval_rows"]) == 2
    assert result["summary"]["topline"]["success_rate"] == 1.0
    assert result["artifacts"]["summary"].endswith("summary.json")


def test_eval_runner_persists_comparison_artifacts(tmp_path) -> None:
    run_results = [
        {
            "policy_name": "baseline",
            "manifest_id": "shared-1",
            "summary": {
                "topline": {
                    "success_rate": 0.0,
                    "repairable_success_rate": 0.0,
                    "correct_abstention_rate": 0.0,
                    "average_reward": -4.0,
                    "average_retry_count": 0.0,
                    "hallucination_rate": 0.0,
                    "wrong_route_rate": 0.0,
                },
                "safety": {"incorrect_abstain_rate": 0.0},
            },
        },
        {
            "policy_name": "adaptive",
            "manifest_id": "shared-1",
            "summary": {
                "topline": {
                    "success_rate": 1.0,
                    "repairable_success_rate": 1.0,
                    "correct_abstention_rate": 1.0,
                    "average_reward": 11.5,
                    "average_retry_count": 0.0,
                    "hallucination_rate": 0.0,
                    "wrong_route_rate": 0.0,
                },
                "safety": {"incorrect_abstain_rate": 0.0},
            },
        },
    ]

    artifacts = persist_comparison(run_results=run_results, output_dir=str(tmp_path / "comparisons"))

    comparison = json.loads((tmp_path / "comparisons" / "comparison.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "comparisons" / "comparison.md").read_text(encoding="utf-8")

    assert artifacts["comparison_json"].endswith("comparison.json")
    assert comparison["manifest_ids"] == ["shared-1"]
    assert "baseline" in markdown
    assert "adaptive" in markdown
