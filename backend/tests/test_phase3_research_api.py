from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.phase3.research_api import ResearchApiSources, create_phase3_research_router


PATHS = {
    "/api/phase3/research/datasets": "dataset",
    "/api/phase3/research/experiments": "experiment",
    "/api/phase3/research/challengers": "challenger",
    "/api/phase3/research/reports": "report",
    "/api/phase3/research/promotion-reviews": "promotion-review",
}


def client(calls: list[str] | None = None) -> TestClient:
    readers = {}
    for label in PATHS.values():
        def reader(current=label):
            if calls is not None:
                calls.append(current)
            return ({"id": current},)
        readers[label] = reader
    sources = ResearchApiSources(
        datasets=readers["dataset"], experiments=readers["experiment"],
        challengers=readers["challenger"], reports=readers["report"],
        promotion_reviews=readers["promotion-review"],
    )
    app = FastAPI()
    app.include_router(create_phase3_research_router(sources))
    return TestClient(app)


def test_all_required_collections_are_exposed_as_read_only_gets() -> None:
    api = client()
    for path, label in PATHS.items():
        response = api.get(path)
        assert response.status_code == 200
        assert response.json() == {
            "count": 1, "execution_authorized": False, "items": [{"id": label}],
            "production_mutation_authorized": False, "read_only": True,
        }


def test_each_get_invokes_only_its_matching_reader() -> None:
    calls: list[str] = []
    api = client(calls)
    api.get("/api/phase3/research/reports")
    assert calls == ["report"]


def test_router_has_no_mutating_http_methods() -> None:
    api = client()
    documented = api.get("/openapi.json").json()["paths"]
    research_routes = {path: methods for path, methods in documented.items() if path.startswith("/api/phase3/research")}
    assert len(research_routes) == 5
    assert all(set(methods) == {"get"} for methods in research_routes.values())
    for path in PATHS:
        assert api.post(path, json={}).status_code == 405
        assert api.delete(path).status_code == 405


def test_reader_failure_or_invalid_payload_fails_closed() -> None:
    def broken():
        raise RuntimeError("storage unavailable")
    sources = ResearchApiSources(broken, broken, broken, broken, broken)
    app = FastAPI()
    app.include_router(create_phase3_research_router(sources))
    response = TestClient(app).get("/api/phase3/research/datasets")
    assert response.status_code == 503
    assert response.json()["detail"] == "RESEARCH_READ_MODEL_UNAVAILABLE"


def test_payload_is_detached_from_provider_mapping() -> None:
    source = {"id": "dataset", "nested": {"value": 1}}
    sources = ResearchApiSources(lambda: (source,), lambda: (), lambda: (), lambda: (), lambda: ())
    app = FastAPI()
    app.include_router(create_phase3_research_router(sources))
    payload = TestClient(app).get("/api/phase3/research/datasets").json()
    source["nested"]["value"] = 2
    assert payload["items"][0]["nested"]["value"] == 1
