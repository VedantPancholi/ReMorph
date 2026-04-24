"""Canonical experiment manifests for Sprint 4 Phase 2 protocol."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sprint4.training.benchmark_contract import BENCHMARK_CONTRACT_VERSION
from sprint4.training.split_strategy import build_group_id, split_rows_grouped, summarize_split


def build_experiment_manifests(
    *,
    supervised_rows: list[dict[str, Any]],
    transition_rows: list[dict[str, Any]],
    split_seed: int = 42,
    eval_ratio: float = 0.2,
) -> dict[str, dict[str, Any]]:
    """Build canonical manifests for supervised train, transition train, and shared eval."""

    combined_rows = _dedupe_combined_rows(supervised_rows, transition_rows)
    _, eval_rows, assignments = split_rows_grouped(
        combined_rows,
        eval_ratio=eval_ratio,
        seed=split_seed,
    )
    eval_groups = {
        build_group_id(row)
        for row in eval_rows
    }

    supervised_train = [
        row for row in supervised_rows
        if build_group_id(row) not in eval_groups
    ]
    transition_train = [
        row for row in transition_rows
        if build_group_id(row) not in eval_groups
    ]
    shared_eval_supervised = [
        row for row in supervised_rows
        if build_group_id(row) in eval_groups
    ]
    shared_eval_transition = [
        row for row in transition_rows
        if build_group_id(row) in eval_groups
    ]

    return {
        "supervised_train": _build_manifest(
            manifest_kind="supervised_train",
            rows=supervised_train,
            split_seed=split_seed,
            eval_ratio=eval_ratio,
            assignments=assignments,
        ),
        "transition_train": _build_manifest(
            manifest_kind="transition_train",
            rows=transition_train,
            split_seed=split_seed,
            eval_ratio=eval_ratio,
            assignments=assignments,
        ),
        "shared_eval": _build_shared_eval_manifest(
            supervised_rows=shared_eval_supervised,
            transition_rows=shared_eval_transition,
            split_seed=split_seed,
            eval_ratio=eval_ratio,
            assignments=assignments,
        ),
    }


def _build_manifest(
    *,
    manifest_kind: str,
    rows: list[dict[str, Any]],
    split_seed: int,
    eval_ratio: float,
    assignments: dict[str, str],
) -> dict[str, Any]:
    descriptors = [_row_descriptor(row) for row in rows]
    summary = summarize_split(rows)
    manifest_id = _manifest_id(manifest_kind, descriptors, split_seed)
    return {
        "manifest_id": manifest_id,
        "manifest_kind": manifest_kind,
        "contract_version": BENCHMARK_CONTRACT_VERSION,
        "split_seed": split_seed,
        "eval_ratio": eval_ratio,
        "generation_timestamp": datetime.now(UTC).isoformat(),
        "total_rows": len(rows),
        "counts_by_split": _counts_by_split(rows, assignments),
        "counts_by_source": summary["source_distribution"],
        "counts_by_scenario": summary["scenario_distribution"],
        "counts_by_partition": summary["partition_distribution"],
        "row_descriptors": descriptors,
    }


def _build_shared_eval_manifest(
    *,
    supervised_rows: list[dict[str, Any]],
    transition_rows: list[dict[str, Any]],
    split_seed: int,
    eval_ratio: float,
    assignments: dict[str, str],
) -> dict[str, Any]:
    supervised_descriptors = [_row_descriptor(row) | {"row_type": "supervised"} for row in supervised_rows]
    transition_descriptors = [_row_descriptor(row) | {"row_type": "transition"} for row in transition_rows]
    combined_rows = supervised_rows + transition_rows
    summary = summarize_split(combined_rows)
    manifest_id = _manifest_id("shared_eval", supervised_descriptors + transition_descriptors, split_seed)
    return {
        "manifest_id": manifest_id,
        "manifest_kind": "shared_eval",
        "contract_version": BENCHMARK_CONTRACT_VERSION,
        "split_seed": split_seed,
        "eval_ratio": eval_ratio,
        "generation_timestamp": datetime.now(UTC).isoformat(),
        "total_rows": len(combined_rows),
        "counts_by_split": _counts_by_split(combined_rows, assignments),
        "counts_by_source": summary["source_distribution"],
        "counts_by_scenario": summary["scenario_distribution"],
        "counts_by_partition": summary["partition_distribution"],
        "supervised_row_descriptors": supervised_descriptors,
        "transition_row_descriptors": transition_descriptors,
    }


def _counts_by_split(rows: list[dict[str, Any]], assignments: dict[str, str]) -> dict[str, int]:
    counts = {"train": 0, "eval": 0}
    for row in rows:
        counts[assignments.get(build_group_id(row), "train")] += 1
    return counts


def _row_descriptor(row: dict[str, Any]) -> dict[str, Any]:
    provenance = row.get("provenance") or {}
    return {
        "episode_id": row.get("episode_id"),
        "group_id": build_group_id(row),
        "raw_scenario_type": row.get("raw_scenario_type"),
        "benchmark_partition": row.get("benchmark_partition"),
        "source_name": provenance.get("source_name", "unknown"),
        "source_record_id": provenance.get("source_record_id"),
    }


def _manifest_id(
    manifest_kind: str,
    descriptors: list[dict[str, Any]],
    split_seed: int,
) -> str:
    payload = json.dumps(
        {
            "manifest_kind": manifest_kind,
            "split_seed": split_seed,
            "descriptors": descriptors,
        },
        sort_keys=True,
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _dedupe_combined_rows(
    supervised_rows: list[dict[str, Any]],
    transition_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}
    for row in supervised_rows + transition_rows:
        combined.setdefault(build_group_id(row), row)
    return list(combined.values())
