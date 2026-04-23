import pytest

from sprint4.env.factory import LiveEnvConfig, OpenEnvClientConfig, build_environment
from sprint4.env.live_api_env import LiveAPIEnvironment
from sprint4.env.mutable_api_env import MutableAPIEnvironment
from sprint4.env.scenario_loader import load_contract_bundle


def test_factory_builds_simulated_backend() -> None:
    bundle = load_contract_bundle()
    env = build_environment(bundle=bundle, backend="simulated")
    assert isinstance(env, MutableAPIEnvironment)


def test_factory_builds_live_backend() -> None:
    bundle = load_contract_bundle()
    env = build_environment(
        bundle=bundle,
        backend="live",
        live_config=LiveEnvConfig(base_url="http://127.0.0.1:8000"),
    )
    assert isinstance(env, LiveAPIEnvironment)
    assert env._baseline_contract["openapi"].startswith("3.")


def test_factory_requires_live_config() -> None:
    bundle = load_contract_bundle()
    with pytest.raises(ValueError):
        build_environment(bundle=bundle, backend="live", live_config=None)


def test_factory_requires_openenv_config() -> None:
    bundle = load_contract_bundle()
    with pytest.raises(ValueError):
        build_environment(bundle=bundle, backend="openenv", openenv_config=None)


def test_factory_raises_when_openenv_client_module_missing() -> None:
    bundle = load_contract_bundle()
    with pytest.raises(ModuleNotFoundError):
        build_environment(
            bundle=bundle,
            backend="openenv",
            openenv_config=OpenEnvClientConfig(
                module="missing_openenv_module_for_test",
                class_name="MissingClient",
            ),
        )
