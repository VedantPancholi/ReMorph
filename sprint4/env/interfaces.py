"""Shared environment interface used by Sprint 4 runtime code."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class APIEnvironment(ABC):
    """Minimal contract shared by the simulated and OpenEnv backends."""

    @abstractmethod
    def reset(self) -> None:
        """Reset the environment to its baseline state."""

    @abstractmethod
    def apply_drift(self, drift_mode: str) -> None:
        """Activate one drift mode for the next episode."""

    @abstractmethod
    def execute_request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        """Execute one HTTP-like request against the active environment."""

    @abstractmethod
    def expected_route_for_method(self, method: str) -> str | None:
        """Return the active route expected for the given method."""

    @abstractmethod
    def is_payload_hallucinated(self, payload: dict[str, Any], route: str) -> bool:
        """Return True when the payload introduces fields outside the active contract."""
