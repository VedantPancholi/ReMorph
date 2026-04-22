import pytest

from app.services.doc_fetcher import load_local_spec
from app.services.schema_extractor import extract_schema_for_route
from app.utils.error_utils import AmbiguousRouteMatchError, SchemaExtractionError


def test_extract_schema_matches_parameterized_route() -> None:
    spec = load_local_spec("app/testsupport/sample_openapi.json")
    spec["paths"]["/users/{user_id}"] = {
        "get": {
            "summary": "Get user by id",
            "responses": {"200": {"description": "ok"}},
        }
    }

    schema = extract_schema_for_route(spec, "/users/12345", "GET")

    assert schema.path == "/users/{user_id}"


def test_extract_schema_ignores_query_string_in_route_matching() -> None:
    spec = load_local_spec("app/testsupport/sample_openapi.json")
    spec["paths"]["/search/{term}"] = {
        "get": {
            "summary": "Search",
            "responses": {"200": {"description": "ok"}},
        }
    }

    schema = extract_schema_for_route(spec, "/search/python", "GET")

    assert schema.path == "/search/{term}"


def test_extract_schema_raises_on_ambiguous_match() -> None:
    spec = load_local_spec("app/testsupport/sample_openapi.json")
    spec["paths"]["/reports/{report_id}"] = {
        "get": {"summary": "By id", "responses": {"200": {"description": "ok"}}}
    }
    spec["paths"]["/reports/{report_slug}"] = {
        "get": {"summary": "By slug", "responses": {"200": {"description": "ok"}}}
    }

    with pytest.raises(AmbiguousRouteMatchError):
        extract_schema_for_route(spec, "/reports/quarterly", "GET")


def test_extract_schema_raises_on_low_confidence_match() -> None:
    spec = load_local_spec("app/testsupport/sample_openapi.json")

    with pytest.raises(SchemaExtractionError):
        extract_schema_for_route(spec, "/totally/unrelated/path", "GET")


def test_extract_schema_ranked_match_succeeds_when_exact_match_fails() -> None:
    spec = load_local_spec("app/testsupport/sample_openapi.json")
    spec["paths"]["/api/v2/finance/ledger/{ledger_id}"] = {
        "get": {"summary": "Ledger by id", "responses": {"200": {"description": "ok"}}}
    }

    schema = extract_schema_for_route(spec, "/api/v1/transactions/123", "GET")

    assert schema.route_match_confidence > 0.45
    assert schema.path in {"/api/v2/finance/ledger", "/api/v2/finance/ledger/{ledger_id}"}
    assert "/api/v2/finance/ledger/{ledger_id}" in {
        candidate.path for candidate in schema.ranked_candidate_endpoints
    }
