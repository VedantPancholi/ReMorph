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


class QueryParameter(BaseModel):
    """Normalized query/path/header parameter metadata from OpenAPI."""

    name: str
    location: str
    required: bool = False
    schema_type: str | None = None


class RouteMatchCandidate(BaseModel):
    """Ranked route candidate returned by schema extraction."""

    path: str
    score: float = Field(ge=0.0)
    reason: str


class SpecMetadata(BaseModel):
    """Metadata describing the documentation source and parse quality."""

    source: str
    candidate_used: str
    fetch_success: bool = False
    parse_success: bool = False
    spec_version: str | None = None
    spec_hash: str | None = None
    fetched_at: str | None = None
    content_type: str | None = None
    source_kind: str = "json"
    completeness_flags: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class EndpointSchema(BaseModel):
    """Slim internal representation of an endpoint contract."""

    path: str
    method: str
    summary: str | None = None
    description: str | None = None
    required_fields: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    request_structure: dict[str, Any] = Field(default_factory=dict)
    query_parameters: list[QueryParameter] = Field(default_factory=list)
    supported_content_types: list[str] = Field(default_factory=list)
    security_requirements: list[SecurityRequirement] = Field(default_factory=list)
    completeness_flags: list[str] = Field(default_factory=list)
    completeness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    docs_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    route_match_score: float = Field(default=0.0, ge=0.0)
    route_match_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    route_match_reason: str = ""
    ranked_candidate_endpoints: list[RouteMatchCandidate] = Field(default_factory=list)
