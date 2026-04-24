"""Deterministic grouped split strategy for Sprint 4 experiment protocol."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlsplit


@dataclass(frozen=True)
class SplitGroup:
    """One leakage-prevention grouping unit."""

    group_id: str
    rows: list[dict[str, Any]]
    raw_scenario_type: str
    benchmark_partition: str
    source_name: str


def build_group_id(row: dict[str, Any]) -> str:
    """Return the canonical leakage-prevention group id for one row."""

    if row.get("group_id"):
        return str(row["group_id"])

    scenario_fingerprint = _build_scenario_fingerprint_payload(row)
    if scenario_fingerprint is not None:
        fingerprint = hashlib.sha256(
            json.dumps(scenario_fingerprint, sort_keys=True, ensure_ascii=True).encode("utf-8")
        ).hexdigest()[:16]
        return f"scenario:{fingerprint}"

    if row.get("episode_id"):
        return str(row["episode_id"])

    provenance = row.get("provenance") or {}
    source_name = str(provenance.get("source_name") or "unknown")
    source_record_id = provenance.get("source_record_id")
    if source_record_id:
        return f"{source_name}:{source_record_id}"

    fingerprint_payload = {
        "raw_scenario_type": row.get("raw_scenario_type"),
        "benchmark_partition": row.get("benchmark_partition"),
        "target_action": row.get("target_action"),
        "action": row.get("action"),
        "state": row.get("state"),
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()[:16]
    return f"fingerprint:{fingerprint}"


def split_rows_grouped(
    rows: list[dict[str, Any]],
    *,
    eval_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    """Split rows into train/eval with grouped leakage prevention and stratification."""

    groups = _build_groups(rows)
    eval_group_ids = _select_eval_groups(groups, eval_ratio=eval_ratio, seed=seed)
    assignments = {
        group.group_id: ("eval" if group.group_id in eval_group_ids else "train")
        for group in groups
    }
    train_rows: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []
    for row in rows:
        if assignments[build_group_id(row)] == "eval":
            eval_rows.append(row)
        else:
            train_rows.append(row)
    return train_rows, eval_rows, assignments


def summarize_split(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a compact distribution summary for one split."""

    scenario_counts: Counter[str] = Counter()
    partition_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    group_ids = set()

    for row in rows:
        scenario_counts[str(row.get("raw_scenario_type") or "unknown")] += 1
        partition_counts[str(row.get("benchmark_partition") or "other")] += 1
        provenance = row.get("provenance") or {}
        source_counts[str(provenance.get("source_name") or "unknown")] += 1
        group_ids.add(build_group_id(row))

    return {
        "row_count": len(rows),
        "group_count": len(group_ids),
        "scenario_distribution": dict(scenario_counts),
        "partition_distribution": dict(partition_counts),
        "source_distribution": dict(source_counts),
    }


def _build_groups(rows: list[dict[str, Any]]) -> list[SplitGroup]:
    grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped_rows[build_group_id(row)].append(row)

    groups: list[SplitGroup] = []
    for group_id, items in grouped_rows.items():
        first = items[0]
        provenance = first.get("provenance") or {}
        groups.append(
            SplitGroup(
                group_id=group_id,
                rows=items,
                raw_scenario_type=str(first.get("raw_scenario_type") or "unknown"),
                benchmark_partition=str(first.get("benchmark_partition") or "other"),
                source_name=str(provenance.get("source_name") or "unknown"),
            )
        )
    return groups


def _select_eval_groups(
    groups: list[SplitGroup],
    *,
    eval_ratio: float,
    seed: int,
) -> set[str]:
    strata: dict[tuple[str, str], list[SplitGroup]] = defaultdict(list)
    for group in groups:
        strata[(group.raw_scenario_type, group.benchmark_partition)].append(group)

    selected: set[str] = set()
    for stratum_groups in strata.values():
        ordered = sorted(
            stratum_groups,
            key=lambda group: _stable_seeded_score(group.group_id, seed),
        )
        if len(ordered) <= 1:
            continue
        target_eval = int(round(len(ordered) * eval_ratio))
        target_eval = max(1, target_eval) if eval_ratio > 0 else 0
        target_eval = min(target_eval, len(ordered) - 1)
        selected.update(group.group_id for group in ordered[:target_eval])

    overall_target = int(round(len(groups) * eval_ratio))
    overall_target = max(1, overall_target) if eval_ratio > 0 and len(groups) > 1 else 0
    overall_target = min(overall_target, max(0, len(groups) - 1))
    if len(selected) < overall_target:
        ordered_groups = sorted(
            groups,
            key=lambda group: _stable_seeded_score(group.group_id, seed),
        )
        for group in ordered_groups:
            if group.group_id in selected:
                continue
            selected.add(group.group_id)
            if len(selected) >= overall_target:
                break
    return selected


def _stable_seeded_score(value: str, seed: int) -> str:
    payload = f"{seed}:{value}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _build_scenario_fingerprint_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    provenance = row.get("provenance") or {}
    state = row.get("state") or {}
    if state:
        request_path = state.get("request_path")
        request_method = state.get("request_method")
        if request_path and request_method:
            return {
                "raw_scenario_type": row.get("raw_scenario_type") or state.get("raw_scenario_type") or "unknown",
                "benchmark_partition": row.get("benchmark_partition") or state.get("benchmark_partition") or "other",
                "scenario_type": state.get("scenario_type") or "unknown",
                "request_method": str(request_method).upper(),
                "request_path": str(request_path),
                "request_query": dict(state.get("request_query") or {}),
                "request_body": state.get("request_body"),
                "source_name": str(provenance.get("source_name") or "unknown"),
            }

    original_request = row.get("original_request") or {}
    if original_request.get("url") and original_request.get("method"):
        parts = urlsplit(str(original_request.get("url")))
        return {
            "raw_scenario_type": row.get("raw_scenario_type") or original_request.get("raw_scenario_type") or "unknown",
            "benchmark_partition": row.get("benchmark_partition") or "other",
            "request_method": str(original_request.get("method")).upper(),
            "request_path": parts.path or "/",
            "request_query": dict(parse_qsl(parts.query, keep_blank_values=True)),
            "request_body": original_request.get("payload"),
            "source_name": str(provenance.get("source_name") or "unknown"),
        }

    return None
