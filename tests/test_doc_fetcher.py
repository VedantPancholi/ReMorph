from app.services.doc_fetcher import load_local_spec


def test_load_local_spec_reads_sample_openapi() -> None:
    spec = load_local_spec("app/testsupport/sample_openapi.json")
    assert spec["info"]["title"] == "ReMorph Demo API"
