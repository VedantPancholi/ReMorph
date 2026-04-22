from app.services.doc_fetcher import load_local_spec
from app.services.schema_extractor import extract_schema_for_route


def test_extract_schema_for_nested_user_payload() -> None:
    spec = load_local_spec("app/testsupport/sample_openapi.json")
    schema = extract_schema_for_route(spec, "/users", "POST")

    assert schema.path == "/users"
    assert schema.required_fields == ["user"]
    assert "user" in schema.request_structure["properties"]
    assert schema.supported_content_types == ["application/json"]
    assert schema.completeness_score > 0.5
    assert schema.docs_confidence > 0.5


def test_extract_schema_for_route_drift_target() -> None:
    spec = load_local_spec("app/testsupport/sample_openapi.json")
    schema = extract_schema_for_route(spec, "/api/v1/transactions", "GET")

    assert schema.path == "/api/v2/finance/ledger"
    assert schema.security_requirements[0].header_name == "x-api-key"
    assert schema.route_match_score > 0.45
