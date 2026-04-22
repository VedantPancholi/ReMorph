"""Normalized schema models produced from OpenAPI documents."""

from typing import Any

from pydantic import BaseModel, Field


class SecurityRequirement(BaseModel):
    """Normalized authentication requirement."""

    name: str
    type: str | None = None
    location: str | None = None
    scheme: str | None = None
    header_name: str | None = None


class EndpointSchema(BaseModel):
    """Slim internal representation of an endpoint contract."""

    path: str
    method: str
    summary: str | None = None
    description: str | None = None
    required_fields: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    request_structure: dict[str, Any] = Field(default_factory=dict)
    security_requirements: list[SecurityRequirement] = Field(default_factory=list)
