"""Environment backend factory for Sprint 4."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Literal

from sprint4.env.interfaces import APIEnvironment
from sprint4.env.mutable_api_env import MutableAPIEnvironment
from sprint4.env.openenv_adapter import OpenEnvAPIEnvironment
from sprint4.env.scenario_loader import ContractBundle

EnvironmentBackend = Literal["simulated", "openenv"]


@dataclass(frozen=True)
class OpenEnvClientConfig:
    """Settings needed to construct an OpenEnv client."""

    module: str
    class_name: str
    base_url: str | None = None
    strict: bool = False


def build_environment(
    *,
    bundle: ContractBundle,
    backend: EnvironmentBackend,
    openenv_config: OpenEnvClientConfig | None = None,
) -> APIEnvironment:
    """Build the selected runtime backend."""
    if backend == "simulated":
        return MutableAPIEnvironment(
            baseline_contract=bundle.baseline_contract,
            drift_contracts=bundle.drift_contracts,
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
