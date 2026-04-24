"""Policy adapter utilities for Sprint 4 Phase 2 training and evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from app.services.doc_fetcher import load_local_spec
from sprint4.training.benchmark_contract import (
    BENCHMARK_CONTRACT_VERSION,
    classify_raw_scenario,
    is_repairable,
    is_unrecoverable,
)
from sprint4.training.dataset_schema import CandidateRoute, PolicyAction, PolicyState


@dataclass(frozen=True)
class PolicyBatch:
    """Minimal policy training batch format."""

    prompts: list[str]
    completions: list[str]
    rewards: list[float]
    metadata: list[dict[str, Any]]


def build_policy_batch(samples: list[dict[str, Any]]) -> PolicyBatch:
    """Create a policy batch from GRPO-style samples."""
    return PolicyBatch(
        prompts=[str(sample["prompt"]) for sample in samples],
        completions=[str(sample["completion"]) for sample in samples],
        rewards=[float(sample["reward"]) for sample in samples],
        metadata=[
            {
                "scenario_type": sample.get("scenario_type"),
                "raw_scenario_type": sample.get("raw_scenario_type"),
                "benchmark_partition": sample.get("metadata", {}).get("benchmark_partition"),
                "success": sample.get("success"),
                "reward": sample.get("reward"),
            }
            for sample in samples
        ],
    )


def episode_to_policy_state(episode: dict[str, Any]) -> PolicyState:
    """Normalize one benchmark episode into a policy-facing state object."""

    original_request = episode.get("original_request") or {}
    trapped_error = episode.get("trapped_error") or {}
    raw_scenario_type = str(episode.get("raw_scenario_type") or "unknown")
    partition = classify_raw_scenario(raw_scenario_type) or "other"
    url = str(
        original_request.get("url")
        or trapped_error.get("target_url")
        or ""
    )
    parts = urlsplit(url)
    request_method = str(
        original_request.get("method")
        or trapped_error.get("method")
        or "GET"
    ).upper()

    return PolicyState(
        episode_id=str(episode.get("request_id") or _episode_id_from_request(original_request, trapped_error)),
        scenario_type=str(episode.get("scenario_type") or "unknown"),
        raw_scenario_type=raw_scenario_type,
        benchmark_partition=partition,
        contract_version=BENCHMARK_CONTRACT_VERSION,
        request_method=request_method,
        request_path=parts.path or "/",
        request_headers=dict(original_request.get("headers") or trapped_error.get("failed_headers") or {}),
        request_query=_query_from_episode(parts.query, trapped_error),
        request_body=original_request.get("payload") or trapped_error.get("failed_payload"),
        failure_code=episode.get("error_code") or trapped_error.get("error_code"),
        failure_message=episode.get("error_message") or trapped_error.get("error_message"),
        failure_signals=dict(trapped_error.get("failure_signals") or {}),
        candidate_routes=_candidate_routes_from_episode(episode, request_method),
        contract_hints=_contract_hints_from_episode(episode),
        retry_count=int(trapped_error.get("retry_count") or 0),
    )


def episode_to_policy_action(episode: dict[str, Any]) -> PolicyAction:
    """Project one benchmark episode into a structured policy action."""

    raw_scenario_type = str(episode.get("raw_scenario_type") or "unknown")
    healed_method = episode.get("healed_method")
    healed_url = episode.get("healed_url")
    healed_headers = episode.get("healed_headers")
    healed_payload = episode.get("healed_payload")
    selected_endpoint = episode.get("selected_endpoint_path")
    reasoning = episode.get("reasoning") or episode.get("unrecoverable_reason")
    healing_action = str(episode.get("healing_action") or "no_change")

    if healing_action == "safe_abstain":
        return PolicyAction(
            action_type="abstain",
            reason=str(
                reasoning or "Unsafe to fabricate missing or invalid credential material."
            ),
        )

    if is_unrecoverable(raw_scenario_type):
        return PolicyAction(
            action_type="abstain",
            reason=reasoning or "Unsafe to fabricate a repair for an unrecoverable auth scenario.",
        )

    if healing_action == "route_rewrite":
        return PolicyAction(
            action_type="repair_route",
            target_method=str(healed_method).upper() if healed_method else None,
            target_path=_path_from_url(healed_url),
            query_patch=_query_patch_from_urls(
                original_url=(episode.get("original_request") or {}).get("url"),
                healed_url=healed_url,
            ),
            reason=reasoning,
        )
    if healing_action == "payload_rewrite":
        return PolicyAction(
            action_type="repair_payload",
            target_method=str(healed_method).upper() if healed_method else None,
            target_path=selected_endpoint or _path_from_url(healed_url),
            body_patch=healed_payload,
            reason=reasoning,
        )
    if healing_action == "auth_rewrite":
        return PolicyAction(
            action_type="repair_auth",
            target_method=str(healed_method).upper() if healed_method else None,
            target_path=selected_endpoint or _path_from_url(healed_url),
            header_patch=healed_headers,
            reason=reasoning,
        )
    if healing_action == "combined_rewrite":
        return PolicyAction(
            action_type=_combined_action_type(episode),
            target_method=str(healed_method).upper() if healed_method else None,
            target_path=selected_endpoint or _path_from_url(healed_url),
            header_patch=healed_headers,
            query_patch=_query_patch_from_urls(
                original_url=(episode.get("original_request") or {}).get("url"),
                healed_url=healed_url,
            ),
            body_patch=healed_payload,
            reason=reasoning,
        )
    if is_repairable(raw_scenario_type):
        return PolicyAction(
            action_type="no_op",
            target_method=str(healed_method).upper() if healed_method else None,
            target_path=selected_endpoint or _path_from_url(healed_url),
            reason=reasoning or "No policy action was recorded.",
        )
    return PolicyAction(action_type="abstain", reason=reasoning)


def build_policy_example(episode: dict[str, Any]) -> tuple[PolicyState, PolicyAction]:
    """Return the normalized state/action pair for one benchmark episode."""

    return episode_to_policy_state(episode), episode_to_policy_action(episode)


def episode_to_rl_transition(episode: dict[str, Any]) -> dict[str, Any]:
    """Convert one episode record into an RL-style transition."""

    state = episode_to_policy_state(episode)
    action = episode_to_policy_action(episode)
    observation = {
        "failed_request": dict(episode.get("original_request") or {}),
        "error_code": state.failure_code,
        "error_message": state.failure_message,
        "contract_schema_summary": _contract_schema_summary_from_episode(episode),
        "candidate_routes": [
            candidate.model_dump(mode="json")
            for candidate in state.candidate_routes
        ],
        "scenario_type": state.scenario_type,
        "retry_count": state.retry_count,
    }
    transition_action = {
        "repair_type": str(episode.get("healing_action") or action.action_type),
        "selected_endpoint": episode.get("selected_endpoint_path"),
        "method_rewrite": bool(
            episode.get("healed_method")
            and str(episode.get("healed_method")).upper() != state.request_method
        ),
        "payload_rewrite": bool(episode.get("healed_payload")),
        "auth_rewrite": bool(episode.get("healed_headers")),
        "safe_abstain": bool(episode.get("healing_action") == "safe_abstain"),
    }
    reward_breakdown = dict(episode.get("reward_breakdown") or {})
    reward = float(
        reward_breakdown.get("final_reward", episode.get("reward", 0.0)) or 0.0
    )
    info = {
        "success": bool(episode.get("success", False)),
        "final_status_code": episode.get("final_status_code"),
        "retries_used": int(episode.get("retries_used", 0) or 0),
        "reward_breakdown": reward_breakdown,
        "recoverable": episode.get("recoverable"),
        "unrecoverable_reason": episode.get("unrecoverable_reason"),
        "raw_scenario_type": episode.get("raw_scenario_type"),
        "agent_type": episode.get("agent_type"),
    }
    return {
        "observation": observation,
        "action": transition_action,
        "reward": reward,
        "done": True,
        "info": info,
    }


def openenv_step_to_rl_transition(
    step_result: dict[str, Any],
    *,
    observation: dict[str, Any] | None = None,
    action: dict[str, Any] | None = None,
    done: bool = False,
) -> dict[str, Any]:
    """Convert an OpenEnv-like step result into the RL-facing format."""

    reward_breakdown = dict(step_result.get("reward_breakdown") or {})
    reward = float(
        step_result.get(
            "reward",
            reward_breakdown.get("final_reward", reward_breakdown.get("reward_total", 0.0)),
        )
        or 0.0
    )
    return {
        "observation": observation or dict(step_result.get("observation") or {}),
        "action": action or dict(step_result.get("action") or {}),
        "reward": reward,
        "done": bool(step_result.get("done", done)),
        "info": {
            "success": bool(step_result.get("success", False)),
            "status_code": step_result.get("status_code"),
            "reward_breakdown": reward_breakdown,
            "raw_step_result": step_result,
        },
    }


def _query_from_episode(query_string: str, trapped_error: dict[str, Any]) -> dict[str, Any]:
    params = dict(parse_qsl(query_string, keep_blank_values=True))
    params.update(
        {
            key: value
            for key, value in (trapped_error.get("query_params") or {}).items()
            if value is not None
        }
    )
    return params


def _candidate_routes_from_episode(
    episode: dict[str, Any],
    request_method: str,
) -> list[CandidateRoute]:
    selected_endpoint = episode.get("selected_endpoint_path")
    confidence = episode.get("route_match_confidence")
    candidates: list[CandidateRoute] = []
    if selected_endpoint:
        candidates.append(
            CandidateRoute(
                path=str(selected_endpoint),
                method=request_method,
                confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
                source="selected_endpoint",
            )
        )
    healed_url = episode.get("healed_url")
    healed_path = _path_from_url(healed_url)
    if healed_path and healed_path != selected_endpoint:
        candidates.append(
            CandidateRoute(
                path=healed_path,
                method=str(episode.get("healed_method") or request_method).upper(),
                source="healed_request",
            )
        )
    return candidates


def _contract_hints_from_episode(episode: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_endpoint_path": episode.get("selected_endpoint_path"),
        "route_match_confidence": episode.get("route_match_confidence"),
        "repair_strategy": episode.get("repair_strategy"),
        "healing_action": episode.get("healing_action"),
        "recoverable": episode.get("recoverable"),
        "unrecoverable_reason": episode.get("unrecoverable_reason"),
        "reward_breakdown": dict(episode.get("reward_breakdown") or {}),
    }


def _contract_schema_summary_from_episode(episode: dict[str, Any]) -> dict[str, Any] | None:
    local_spec_path = episode.get("local_spec_path")
    endpoint_path = episode.get("selected_endpoint_path") or _path_from_url(episode.get("healed_url"))
    method = (
        episode.get("healed_method")
        or (episode.get("original_request") or {}).get("method")
        or (episode.get("trapped_error") or {}).get("method")
    )
    if not local_spec_path or not endpoint_path or not method:
        return None
    try:
        spec = load_local_spec(str(local_spec_path))
    except Exception:
        return None

    operation = (
        spec.get("paths", {})
        .get(str(endpoint_path), {})
        .get(str(method).lower())
    )
    if not isinstance(operation, dict):
        return None
    request_body = operation.get("requestBody", {})
    content = request_body.get("content", {})
    schema = None
    if isinstance(content, dict):
        json_body = content.get("application/json")
        if isinstance(json_body, dict):
            schema = json_body.get("schema")
    return {
        "path": str(endpoint_path),
        "method": str(method).upper(),
        "summary": operation.get("summary"),
        "required_headers": _required_headers_from_operation(spec, operation),
        "request_schema": schema if isinstance(schema, dict) else None,
    }


def _query_patch_from_urls(
    *,
    original_url: str | None,
    healed_url: str | None,
) -> dict[str, Any] | None:
    original_query = dict(parse_qsl(urlsplit(str(original_url or "")).query, keep_blank_values=True))
    healed_query = dict(parse_qsl(urlsplit(str(healed_url or "")).query, keep_blank_values=True))
    patch = {
        key: value
        for key, value in healed_query.items()
        if original_query.get(key) != value
    }
    return patch or None


def _combined_action_type(episode: dict[str, Any]) -> str:
    if episode.get("healed_payload"):
        return "repair_payload"
    if episode.get("healed_headers"):
        return "repair_auth"
    return "repair_route"


def _path_from_url(url: Any) -> str | None:
    if not url:
        return None
    path = urlsplit(str(url)).path
    return path or None


def _episode_id_from_request(
    original_request: dict[str, Any],
    trapped_error: dict[str, Any],
) -> str:
    method = str(original_request.get("method") or trapped_error.get("method") or "GET").upper()
    url = str(original_request.get("url") or trapped_error.get("target_url") or "unknown")
    return f"{method}:{url}"


def _required_headers_from_operation(
    spec: dict[str, Any],
    operation: dict[str, Any],
) -> list[str]:
    headers: list[str] = []
    for parameter in operation.get("parameters", []):
        if not isinstance(parameter, dict):
            continue
        if parameter.get("in") == "header" and parameter.get("required") and parameter.get("name"):
            headers.append(str(parameter["name"]))

    security = operation.get("security", spec.get("security", []))
    schemes = spec.get("components", {}).get("securitySchemes", {})
    for requirement in security:
        if not isinstance(requirement, dict):
            continue
        for scheme_name in requirement:
            scheme = schemes.get(scheme_name)
            if not isinstance(scheme, dict):
                continue
            if scheme.get("type") == "apiKey" and scheme.get("in") == "header" and scheme.get("name"):
                headers.append(str(scheme["name"]))
            if scheme.get("type") == "http" and scheme.get("scheme") == "bearer":
                headers.append("Authorization")
    return sorted(set(headers))
