"""Environment backend factory for Sprint 4."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Literal

from app.services.doc_fetcher import load_local_spec
from sprint4.env.interfaces import APIEnvironment
from sprint4.env.live_api_env import LiveAPIEnvironment
from sprint4.env.mutable_api_env import MutableAPIEnvironment
from sprint4.env.openenv_adapter import OpenEnvAPIEnvironment
from sprint4.env.scenario_loader import ContractBundle

EnvironmentBackend = Literal["simulated", "openenv", "live"]
EnvironmentMode = Literal["local", "live"]


@dataclass(frozen=True)
class OpenEnvClientConfig:
    """Settings needed to construct an OpenEnv client."""

    module: str
    class_name: str
    base_url: str | None = None
    strict: bool = False


@dataclass(frozen=True)
class LiveEnvConfig:
    """Settings needed to construct the live FastAPI environment."""

    base_url: str
    spec_path: str = "chaos_gym/specs/openapi.json"


def build_environment(
    *,
    bundle: ContractBundle,
    backend: EnvironmentBackend,
    openenv_config: OpenEnvClientConfig | None = None,
    live_config: LiveEnvConfig | None = None,
) -> APIEnvironment:
    """Build the selected runtime backend."""
    if backend == "simulated":
        return MutableAPIEnvironment(
            baseline_contract=bundle.baseline_contract,
            drift_contracts=bundle.drift_contracts,
        )

    if backend == "live":
        if live_config is None:
            raise ValueError("live_config is required when backend='live'")
        return LiveAPIEnvironment(
            base_url=live_config.base_url,
            baseline_contract=load_local_spec(live_config.spec_path),
        )

    if openenv_config is None:
        raise ValueError("openenv_config is required when backend='openenv'")

    client = _build_openenv_client(openenv_config)
    return OpenEnvAPIEnvironment(
        client=client,
        baseline_contract=bundle.baseline_contract,
        strict=openenv_config.strict,
    )


def _build_openenv_client(config: OpenEnvClientConfig):
    module = import_module(config.module)
    client_class = getattr(module, config.class_name)

    if config.base_url:
        try:
            return client_class(base_url=config.base_url)
        except TypeError:
            return client_class(config.base_url)

    return client_class()


def resolve_backend(
    *,
    backend: EnvironmentBackend | None = None,
    env_mode: EnvironmentMode | None = None,
) -> EnvironmentBackend:
    """Resolve the runtime backend from a local/live mode or direct backend."""

    if env_mode == "local":
        return "simulated"
    if env_mode == "live":
        return "live"
    return backend or "simulated"
