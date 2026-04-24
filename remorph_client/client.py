"""Industry-style ReMorph self-healing API client."""

from __future__ import annotations

from typing import Any

import httpx

from app.models.response_models import HealedRequest
from app.services.doc_fetcher import load_local_spec
from remorph_client.config import ReMorphClientConfig
from sprint4.env.interfaces import APIEnvironment
from sprint4.env.live_api_env import LiveAPIEnvironment
from sprint4.env.live_support import map_scenario_to_category
from sprint4.proxy.request_executor import execute_against_env
from sprint4.proxy.trap_and_repair import package_trapped_error, run_repair
from sprint4.training.benchmark_contract import is_unrecoverable


class ReMorphClient:
    """Thin product-style wrapper over the existing recovery workflow."""

    def __init__(
        self,
        config: ReMorphClientConfig,
        *,
        env: APIEnvironment | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._env = env or LiveAPIEnvironment(
            base_url=config.base_url,
            baseline_contract=load_local_spec(config.openapi_spec_path),
            client=http_client or httpx.Client(timeout=config.timeout_seconds),
            timeout=config.timeout_seconds,
        )

    @classmethod
    def from_config(cls, path: str) -> "ReMorphClient":
        return cls(ReMorphClientConfig.from_file(path))

    def request(
        self,
        *,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        merged_headers = dict(self._config.auth_headers)
        merged_headers.update(headers or {})
        initial = execute_against_env(
            self._env,
            method=method,
            url=path,
            headers=merged_headers,
            payload=json,
        )
        if initial.success:
            return {
                "status": "success",
                "success": True,
                "status_code": initial.status_code,
                "response_body": initial.response_body,
                "repaired": False,
                "retries_used": 0,
                "safe_abstain": False,
            }

        raw_scenario_type = _infer_raw_scenario_type(
            status_code=initial.status_code,
            headers=merged_headers,
        )
        scenario_type = (
            (initial.metadata or {}).get("scenario_type")
            or map_scenario_to_category(
                raw_scenario_type,
                status_code=initial.status_code,
                error_message=initial.error_message,
            )
        )

        if self._config.safe_mode and is_unrecoverable(raw_scenario_type):
            return {
                "status": "safe_abstain",
                "success": False,
                "status_code": initial.status_code,
                "error_message": initial.error_message,
                "repaired": False,
                "retries_used": 0,
                "safe_abstain": True,
                "recoverable": False,
                "unrecoverable_reason": "missing_or_invalid_credential_material",
            }

        current_result = initial
        current_method = method
        current_path = path
        current_headers = merged_headers
        current_payload = json
        healed_request: HealedRequest | None = None
        retries_used = 0
        for cycle in range(1, self._config.max_retries + 1):
            trapped_error = package_trapped_error(
                method=current_method,
                url=current_path,
                payload=current_payload,
                headers=current_headers,
                execution_result=current_result,
                scenario_type=str(scenario_type or "unknown"),
                raw_scenario_type=raw_scenario_type,
                retry_count=cycle - 1,
            )
            repair_result = run_repair(
                trapped_error,
                local_spec_path=self._config.openapi_spec_path,
            )
            healed_request = repair_result.healed_request
            if healed_request is None:
                break
            retries_used += 1
            current_method = healed_request.fixed_method
            current_path = healed_request.fixed_url
            current_headers = healed_request.fixed_headers or {}
            current_payload = healed_request.fixed_payload
            current_result = execute_against_env(
                self._env,
                method=current_method,
                url=current_path,
                headers=current_headers,
                payload=current_payload,
            )
            if current_result.success:
                return {
                    "status": "success",
                    "success": True,
                    "status_code": current_result.status_code,
                    "response_body": current_result.response_body,
                    "repaired": True,
                    "retries_used": retries_used,
                    "safe_abstain": False,
                    "healed_request": healed_request.model_dump(mode="json"),
                }

        return {
            "status": "failed",
            "success": False,
            "status_code": current_result.status_code,
            "error_message": current_result.error_message,
            "repaired": False,
            "retries_used": retries_used,
            "safe_abstain": False,
            "healed_request": healed_request.model_dump(mode="json") if healed_request else None,
        }


def _infer_raw_scenario_type(
    *,
    status_code: int,
    headers: dict[str, str],
) -> str | None:
    if status_code not in {401, 403}:
        return None
    auth_header = str(headers.get("Authorization") or "")
    if not auth_header:
        return "auth_missing_token"
    if not auth_header.lower().startswith("bearer "):
        return "auth_malformed_jwt"
    token = auth_header.split(" ", 1)[1].strip()
    if token.count(".") != 2:
        return "auth_malformed_jwt"
    return "auth_missing_tenant"
