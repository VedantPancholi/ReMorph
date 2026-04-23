"""End-to-end Sprint 4 workflow runner with logging and rewards."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.models.response_models import HealedRequest
from sprint4.env.interfaces import APIEnvironment
from sprint4.proxy.request_executor import RequestExecutionResult, execute_against_env
from sprint4.proxy.trap_and_repair import package_trapped_error, run_repair
from sprint4.rewards.reward_function import RewardFunction, RewardResult, RewardSignals


@dataclass(frozen=True)
class EpisodeRecord:
    """Episode log schema for JSONL persistence and benchmark analysis."""

    scenario_type: str
    original_request: dict[str, Any]
    trapped_error: dict[str, Any] | None
    request_id: str | None
    error_code: int | None
    error_message: str | None
    local_spec_path: str | None
    selected_endpoint_path: str | None
    route_match_confidence: float | None
    repair_strategy: str | None
    healing_action: str | None
    healed_method: str | None
    healed_url: str | None
    healed_payload: dict[str, Any] | None
    healed_headers: dict[str, str] | None
    reasoning: str | None
    cache_hit: bool
    llm_attempted: bool
    llm_succeeded: bool
    retries_used: int
    final_status_code: int
    success: bool
    reward: float
    latency_ms: int
    reward_breakdown: dict[str, float]
    agent_type: str
    environment_mode: str
    raw_scenario_type: str | None = None


@dataclass(frozen=True)
class WorkflowResult:
    """Returned by the runner for live demo and benchmark harnesses."""

    initial_result: RequestExecutionResult
    final_result: RequestExecutionResult
    healed_request: HealedRequest | None
    record: EpisodeRecord
    reward: RewardResult


class WorkflowRunner:
    """Runs baseline or adaptive flow against a mutable environment."""

    def __init__(
        self,
        *,
        env: APIEnvironment,
        reward_function: RewardFunction | None = None,
        episode_log_path: str = "runtime/sprint4/episodes.jsonl",
        max_repair_cycles: int = 2,
        environment_mode: str = "local",
    ) -> None:
        self._env = env
        self._reward_function = reward_function or RewardFunction()
        self._episode_log_path = Path(episode_log_path)
        self._max_repair_cycles = max_repair_cycles
        self._environment_mode = environment_mode

    def run_episode(
        self,
        *,
        scenario_type: str,
        request: dict[str, Any],
        local_spec_path: str,
        adaptive: bool,
    ) -> WorkflowResult:
        start = time.perf_counter()
        initial = execute_against_env(
            self._env,
            method=request["method"],
            url=request["url"],
            headers=request.get("headers"),
            payload=request.get("payload"),
        )
        if not adaptive:
            reward = self._reward_function.score(
                RewardSignals(
                    repaired_success=initial.success,
                    fixed_in_one_cycle=False,
                    extra_retries=0,
                    hallucinated_fields=False,
                    wrong_route_candidate=False,
                    final_recovery_failed=not initial.success,
                )
            )
            record = self._record_episode(
                scenario_type=scenario_type,
                original_request=request,
                trapped_error=None,
                local_spec_path=local_spec_path,
                healed_request=None,
                retries_used=0,
                final_result=initial,
                reward=reward,
                latency_ms=int((time.perf_counter() - start) * 1000),
                agent_type="baseline",
            )
            return WorkflowResult(
                initial_result=initial,
                final_result=initial,
                healed_request=None,
                record=record,
                reward=reward,
            )

        if initial.success:
            reward = self._reward_function.score(
                RewardSignals(
                    repaired_success=True,
                    fixed_in_one_cycle=True,
                    extra_retries=0,
                    hallucinated_fields=False,
                    wrong_route_candidate=False,
                    final_recovery_failed=False,
                )
            )
            record = self._record_episode(
                scenario_type=scenario_type,
                original_request=request,
                trapped_error=None,
                local_spec_path=local_spec_path,
                healed_request=None,
                retries_used=0,
                final_result=initial,
                reward=reward,
                latency_ms=int((time.perf_counter() - start) * 1000),
                agent_type="adaptive",
            )
            return WorkflowResult(
                initial_result=initial,
                final_result=initial,
                healed_request=None,
                record=record,
                reward=reward,
            )

        retries_used = 0
        current_request = dict(request)
        current_result = initial
        trapped_error: dict[str, Any] | None = None
        healed_request: HealedRequest | None = None

        for cycle in range(1, self._max_repair_cycles + 1):
            trapped_error = package_trapped_error(
                method=current_request["method"],
                url=current_request["url"],
                payload=current_request.get("payload"),
                headers=current_request.get("headers"),
                execution_result=current_result,
                scenario_type=scenario_type,
                raw_scenario_type=request.get("raw_scenario_type"),
                retry_count=cycle - 1,
            )
            repair_result = run_repair(trapped_error, local_spec_path=local_spec_path)
            healed_request = repair_result.healed_request
            if healed_request is None:
                break

            current_request = {
                "method": healed_request.fixed_method,
                "url": healed_request.fixed_url,
                "headers": healed_request.fixed_headers,
                "payload": healed_request.fixed_payload,
            }
            retries_used += 1
            current_result = execute_against_env(
                self._env,
                method=current_request["method"],
                url=current_request["url"],
                headers=current_request.get("headers"),
                payload=current_request.get("payload"),
            )
            if current_result.success:
                break

        reward = self._reward_function.score(
            RewardSignals(
                repaired_success=current_result.success,
                fixed_in_one_cycle=current_result.success and retries_used == 1,
                extra_retries=max(0, retries_used - 1),
                hallucinated_fields=self._is_hallucinated_payload(healed_request),
                wrong_route_candidate=self._wrong_route_candidate(healed_request),
                final_recovery_failed=not current_result.success,
            )
        )
        record = self._record_episode(
            scenario_type=scenario_type,
            original_request=request,
            trapped_error=trapped_error,
            local_spec_path=local_spec_path,
            healed_request=healed_request,
            retries_used=retries_used,
            final_result=current_result,
            reward=reward,
            latency_ms=int((time.perf_counter() - start) * 1000),
            agent_type="adaptive",
        )
        return WorkflowResult(
            initial_result=initial,
            final_result=current_result,
            healed_request=healed_request,
            record=record,
            reward=reward,
        )

    def _record_episode(
        self,
        *,
        scenario_type: str,
        original_request: dict[str, Any],
        trapped_error: dict[str, Any] | None,
        local_spec_path: str,
        healed_request: HealedRequest | None,
        retries_used: int,
        final_result: RequestExecutionResult,
        reward: RewardResult,
        latency_ms: int,
        agent_type: str,
    ) -> EpisodeRecord:
        diagnostics = healed_request.diagnostics if healed_request else None
        record = EpisodeRecord(
            scenario_type=scenario_type,
            original_request=original_request,
            trapped_error=trapped_error,
            request_id=(trapped_error or {}).get("request_id"),
            error_code=(trapped_error or {}).get("error_code"),
            error_message=(trapped_error or {}).get("error_message"),
            local_spec_path=local_spec_path,
            selected_endpoint_path=getattr(diagnostics, "selected_endpoint_path", None),
            route_match_confidence=getattr(diagnostics, "docs_confidence", None),
            repair_strategy=getattr(diagnostics, "repair_strategy", None),
            healing_action=getattr(healed_request, "healing_action", None),
            healed_method=getattr(healed_request, "fixed_method", None),
            healed_url=getattr(healed_request, "fixed_url", None),
            healed_payload=getattr(healed_request, "fixed_payload", None),
            healed_headers=getattr(healed_request, "fixed_headers", None),
            reasoning=getattr(healed_request, "reasoning", None),
            cache_hit=getattr(diagnostics, "repair_strategy", "") == "cache",
            llm_attempted=getattr(diagnostics, "llm_attempted", False),
            llm_succeeded=getattr(diagnostics, "llm_succeeded", False),
            retries_used=retries_used,
            final_status_code=final_result.status_code,
            success=final_result.success,
            reward=reward.total_reward,
            latency_ms=latency_ms,
            reward_breakdown=reward.breakdown,
            agent_type=agent_type,
            environment_mode=self._environment_mode,
            raw_scenario_type=(trapped_error or {}).get("raw_scenario_type")
            or original_request.get("raw_scenario_type"),
        )
        self._episode_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._episode_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), ensure_ascii=True) + "\n")
        return record

    def _is_hallucinated_payload(self, healed_request: HealedRequest | None) -> bool:
        if healed_request is None or healed_request.fixed_payload is None:
            return False
        route = urlparse(healed_request.fixed_url).path
        return self._env.is_payload_hallucinated(healed_request.fixed_payload, route)

    def _wrong_route_candidate(self, healed_request: HealedRequest | None) -> bool:
        if healed_request is None:
            return False
        diagnostics = healed_request.diagnostics
        if diagnostics is None:
            return False
        expected_path = self._env.expected_route_for_method(healed_request.fixed_method)
        selected = diagnostics.selected_endpoint_path
        if not selected or not expected_path:
            return False
        return selected != expected_path
