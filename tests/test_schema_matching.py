from app.services.doc_fetcher import load_local_spec
from app.services.schema_extractor import extract_schema_for_route


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
