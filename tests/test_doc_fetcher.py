from app.services.doc_fetcher import load_local_spec, load_local_spec_with_metadata


def test_load_local_spec_reads_sample_openapi() -> None:
    spec = load_local_spec("app/testsupport/sample_openapi.json")
    assert spec["info"]["title"] == "ReMorph Demo API"


def test_load_local_spec_with_metadata_returns_hash_and_version() -> None:
    spec, metadata = load_local_spec_with_metadata("app/testsupport/sample_openapi.json")

    assert spec["openapi"] == "3.0.3"
    assert metadata.fetch_success is True
    assert metadata.parse_success is True
    assert metadata.spec_version == "3.0.3"
    assert metadata.spec_hash is not None
