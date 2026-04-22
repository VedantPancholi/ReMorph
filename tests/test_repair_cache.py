from app.config import get_settings
from app.models.request_models import TrappedError
from app.models.response_models import HealedRequest
from app.services.doc_fetcher import load_local_spec
from app.services.repair_cache import (
    build_repair_cache_key,
    get_cached_repair,
    store_cached_repair,
)
from app.services.schema_extractor import extract_schema_for_route
from app.testsupport.sample_errors import SCENARIO_A_KEY_MUTATION


def test_store_and_load_cached_repair(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REMORPH_REPAIR_CACHE_PATH", str(tmp_path / "repair_cache.json"))
    get_settings.cache_clear()

    trapped_error = TrappedError.model_validate(SCENARIO_A_KEY_MUTATION)
    spec = load_local_spec("app/testsupport/sample_openapi.json")
    endpoint = extract_schema_for_route(spec, "/users", "POST")
    cache_key = build_repair_cache_key(trapped_error, endpoint)

    healed = HealedRequest(
        reasoning="cached repair",
        fixed_url="https://mock.example.com/users",
        fixed_method="POST",
        fixed_payload={"user": {"f_name": "John", "l_name": "Doe"}},
        fixed_headers={"Authorization": "Bearer demo-token"},
        schema_summary={"required_fields": ["user"]},
        healing_action="payload_rewrite",
        confidence=0.9,
    )

    store_cached_repair(cache_key, healed)
    cached = get_cached_repair(cache_key)

    assert cached is not None
    assert cached.fixed_payload == {"user": {"f_name": "John", "l_name": "Doe"}}

    get_settings.cache_clear()
