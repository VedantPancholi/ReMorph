"""Offline normalization bridge for historical Sprint 4 data sources."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from sprint4.training.benchmark_contract import (
    BENCHMARK_CONTRACT_VERSION,
    BenchmarkPartition,
    classify_raw_scenario,
)
from sprint4.training.episode_dataset import (
    build_supervised_row_from_episode,
    build_transition_row_from_episode,
)
from sprint4.training.phase1_dataset_adapter import normalize_phase1_dataset


@dataclass(frozen=True)
class OfflineEpisodeCandidate:
    """One normalized historical record before row export."""

    source_name: str
    source_record_id: str
    raw_episode: dict[str, Any]
    raw_scenario_type: str | None
    benchmark_partition: str | None
    can_build_supervised: bool
    can_build_transition: bool
    validation_errors: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)


def load_phase1_rows(path: str = "target_api/training_dataset.json") -> list[dict[str, Any]]:
    """Load normalized Phase 1 records for offline adaptation."""

    return normalize_phase1_dataset(path)


def load_benchmark_episode_rows(path: str) -> list[dict[str, Any]]:
    """Load episode JSONL rows written by the benchmark runner."""

    from sprint4.training.episode_dataset import load_episode_jsonl

    return load_episode_jsonl(path, agent_type=None)


def adapt_phase1_dataset(
    path: str = "target_api/training_dataset.json",
    *,
    benchmark_partition: BenchmarkPartition = "all",
) -> dict[str, Any]:
    """Adapt the normalized Phase 1 dataset into canonical typed rows."""

    rows = load_phase1_rows(path)
    candidates = [_phase1_row_to_candidate(item, index) for index, item in enumerate(rows)]
    return adapt_offline_sources(
        candidates,
        benchmark_partition=benchmark_partition,
    )


def adapt_benchmark_trace_dataset(
    path: str,
    *,
    benchmark_partition: BenchmarkPartition = "all",
) -> dict[str, Any]:
    """Adapt benchmark episode JSONL into canonical typed rows."""

    rows = load_benchmark_episode_rows(path)
    candidates = [_benchmark_row_to_candidate(item, index) for index, item in enumerate(rows)]
    return adapt_offline_sources(
        candidates,
        benchmark_partition=benchmark_partition,
    )


def adapt_offline_sources(
    candidates: list[OfflineEpisodeCandidate],
    *,
    benchmark_partition: BenchmarkPartition = "all",
) -> dict[str, Any]:
    """Convert normalized offline candidates into canonical typed rows."""

    supervised_rows: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    scenario_counts: Counter[str] = Counter()
    partition_counts: Counter[str] = Counter()
    downgraded_to_supervised_only = 0

    for candidate in candidates:
        source_counts[candidate.source_name] += 1
        if not _candidate_allowed(candidate, benchmark_partition):
            skipped["filtered_partition"] += 1
            continue

        if candidate.validation_errors:
            skipped.update(candidate.validation_errors)

        scenario = str(candidate.raw_scenario_type or "unknown")
        partition = str(candidate.benchmark_partition or "other")

        supervised_row_emitted = False
        supervised_reason: str | None = None
        if candidate.can_build_supervised:
            row, reason = build_supervised_row_from_episode(candidate.raw_episode)
            if row is None:
                supervised_reason = reason or "supervised_build_failed"
                skipped[supervised_reason] += 1
            else:
                dumped = row.model_dump(mode="json")
                dumped["provenance"] = candidate.provenance
                supervised_rows.append(dumped)
                supervised_row_emitted = True
                scenario_counts[scenario] += 1
                partition_counts[partition] += 1
        else:
            skipped["supervised_unavailable"] += 1

        if supervised_reason == "missing_action_trace":
            skipped["transition_unavailable"] += 1
            continue

        if candidate.can_build_transition:
            row, reason = build_transition_row_from_episode(candidate.raw_episode)
            if row is None:
                skipped[reason or "transition_build_failed"] += 1
                if supervised_row_emitted:
                    downgraded_to_supervised_only += 1
            else:
                dumped = row.model_dump(mode="json")
                dumped["provenance"] = candidate.provenance
                transition_rows.append(dumped)
        elif supervised_row_emitted:
            downgraded_to_supervised_only += 1
            skipped["transition_unavailable"] += 1
        else:
            skipped["transition_unavailable"] += 1

    manifest = {
        "total_source_records": len(candidates),
        "supervised_rows_emitted": len(supervised_rows),
        "transition_rows_emitted": len(transition_rows),
        "downgraded_to_supervised_only_count": downgraded_to_supervised_only,
        "skipped_rows_by_reason": dict(skipped),
        "source_distribution": dict(source_counts),
        "scenario_distribution": dict(scenario_counts),
        "partition_distribution": dict(partition_counts),
        "contract_version": BENCHMARK_CONTRACT_VERSION,
        "generation_timestamp": datetime.now(UTC).isoformat(),
    }
    return {
        "supervised_rows": supervised_rows,
        "transition_rows": transition_rows,
        "manifest": manifest,
    }


def build_offline_training_corpus(
    *,
    phase1_dataset_path: str | None = None,
    benchmark_episode_path: str | None = None,
    benchmark_partition: BenchmarkPartition = "all",
) -> dict[str, Any]:
    """Build one offline corpus from whichever supported sources are provided."""

    candidates: list[OfflineEpisodeCandidate] = []
    if phase1_dataset_path:
        candidates.extend(
            _phase1_row_to_candidate(item, index)
            for index, item in enumerate(load_phase1_rows(phase1_dataset_path))
        )
    if benchmark_episode_path:
        candidates.extend(
            _benchmark_row_to_candidate(item, index)
            for index, item in enumerate(load_benchmark_episode_rows(benchmark_episode_path))
        )
    return adapt_offline_sources(candidates, benchmark_partition=benchmark_partition)


def _phase1_row_to_candidate(row: dict[str, Any], index: int) -> OfflineEpisodeCandidate:
    raw_scenario_type = str(row.get("raw_scenario_type") or "unknown")
    contract_partition = classify_raw_scenario(raw_scenario_type)
    source_partition = row.get("metadata", {}).get("benchmark_partition")
    validation_errors: list[str] = []
    if source_partition and contract_partition and source_partition != contract_partition:
        validation_errors.append("contract_partition_mismatch")

    episode = {
        "request_id": row.get("metadata", {}).get("request_id") or f"phase1-{index}",
        "scenario_type": row.get("scenario_type"),
        "raw_scenario_type": raw_scenario_type,
        "original_request": row.get("request") or {},
        "trapped_error": {
            "target_url": row.get("request", {}).get("url"),
            "method": row.get("request", {}).get("method"),
            "failed_payload": row.get("request", {}).get("payload"),
            "failed_headers": row.get("request", {}).get("headers"),
            "error_code": row.get("response", {}).get("status_code"),
            "error_message": row.get("response", {}).get("error_message"),
            "failure_signals": row.get("response", {}).get("failure_signals") or {},
            "retry_count": 0,
            "raw_scenario_type": raw_scenario_type,
        },
        "error_code": row.get("response", {}).get("status_code"),
        "error_message": row.get("response", {}).get("error_message"),
        "final_status_code": row.get("response", {}).get("status_code"),
        "success": bool(row.get("response", {}).get("success", False)),
        "retries_used": 0,
        "local_spec_path": "target_api/specs/openapi.json",
        "selected_endpoint_path": None,
        "route_match_confidence": None,
        "repair_strategy": None,
        "healing_action": _default_healing_action(row.get("scenario_type"), contract_partition),
        "healed_method": row.get("request", {}).get("method"),
        "healed_url": row.get("request", {}).get("url"),
        "healed_payload": row.get("request", {}).get("payload"),
        "healed_headers": row.get("request", {}).get("headers"),
        "reasoning": None,
        "reward_breakdown": {},
        "agent_type": "offline_phase1",
        "environment_mode": row.get("environment_mode"),
    }
    response = row.get("response", {})
    can_build_transition = response.get("status_code") is not None and response.get("success") is not None
    return OfflineEpisodeCandidate(
        source_name="phase1",
        source_record_id=str(row.get("metadata", {}).get("request_id") or f"phase1-{index}"),
        raw_episode=episode,
        raw_scenario_type=raw_scenario_type,
        benchmark_partition=contract_partition,
        can_build_supervised=contract_partition is not None,
        can_build_transition=bool(can_build_transition and contract_partition is not None),
        validation_errors=validation_errors,
        provenance={
            "source_name": "phase1",
            "source_record_id": str(row.get("metadata", {}).get("request_id") or f"phase1-{index}"),
            "adaptation_mode": "normalized_phase1_record",
            "action_inferred_from": "scenario_type",
            "outcome_inferred_from": "response.status_code",
        },
    )


def _benchmark_row_to_candidate(row: dict[str, Any], index: int) -> OfflineEpisodeCandidate:
    raw_scenario_type = str(row.get("raw_scenario_type") or "unknown")
    contract_partition = classify_raw_scenario(raw_scenario_type)
    validation_errors: list[str] = []
    if row.get("raw_scenario_type") and contract_partition is None:
        validation_errors.append("unknown_contract_partition")

    return OfflineEpisodeCandidate(
        source_name="benchmark_episode",
        source_record_id=str(row.get("request_id") or f"benchmark-{index}"),
        raw_episode=row,
        raw_scenario_type=raw_scenario_type,
        benchmark_partition=contract_partition,
        can_build_supervised=contract_partition is not None,
        can_build_transition=(
            contract_partition is not None and row.get("final_status_code") is not None
        ),
        validation_errors=validation_errors,
        provenance={
            "source_name": "benchmark_episode",
            "source_record_id": str(row.get("request_id") or f"benchmark-{index}"),
            "adaptation_mode": "benchmark_episode_passthrough",
            "action_inferred_from": "healed_request_trace",
            "outcome_inferred_from": "final_status_code",
        },
    )


def _candidate_allowed(
    candidate: OfflineEpisodeCandidate,
    benchmark_partition: BenchmarkPartition,
) -> bool:
    if benchmark_partition == "all":
        return candidate.benchmark_partition in {"repairable", "unrecoverable"}
    return candidate.benchmark_partition == benchmark_partition


def _default_healing_action(
    scenario_type: Any,
    contract_partition: str | None,
) -> str | None:
    if contract_partition == "unrecoverable":
        return None
    scenario = str(scenario_type or "")
    if scenario == "route_drift":
        return "route_rewrite"
    if scenario == "payload_drift":
        return "payload_rewrite"
    if scenario == "auth_drift":
        return "auth_rewrite"
    return None
