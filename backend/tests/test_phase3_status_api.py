from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.phase3.status_api import Phase3StatusSources, create_phase3_status_router


NAMES = (
    "runtime_health", "snapshot_ingestion", "evaluation_health",
    "outbox_health", "worker_health", "research_queue_health",
)


def make_client(calls: list[str] | None = None) -> TestClient:
    readers = {}
    for name in NAMES:
        def reader(current=name):
            if calls is not None:
                calls.append(current)
            return {"component": current, "healthy": True}
        readers[name] = reader
    app = FastAPI()
    app.include_router(create_phase3_status_router(Phase3StatusSources(**readers)))
    return TestClient(app)


def test_status_exposes_every_required_health_projection_atomically() -> None:
    payload = make_client().get("/api/phase3/status").json()
    assert set(payload["status"]) == set(NAMES)
    assert all(payload["status"][name]["healthy"] for name in NAMES)
    assert payload["read_only"] is True
    assert payload["execution_authorized"] is False
    assert payload["production_mutation_authorized"] is False


def test_status_calls_each_reader_exactly_once() -> None:
    calls: list[str] = []
    response = make_client(calls).get("/api/phase3/status")
    assert response.status_code == 200
    assert calls == list(NAMES)


def test_any_unavailable_component_fails_without_partial_status() -> None:
    readers = {name: (lambda current=name: {"component": current}) for name in NAMES}
    def broken():
        raise RuntimeError("worker unavailable")
    readers["worker_health"] = broken
    app = FastAPI()
    app.include_router(create_phase3_status_router(Phase3StatusSources(**readers)))
    response = TestClient(app).get("/api/phase3/status")
    assert response.status_code == 503
    assert response.json() == {"detail": "PHASE3_STATUS_UNAVAILABLE"}


def test_invalid_component_payload_fails_closed() -> None:
    readers = {name: (lambda: {}) for name in NAMES}
    readers["outbox_health"] = lambda: []
    app = FastAPI()
    app.include_router(create_phase3_status_router(Phase3StatusSources(**readers)))
    assert TestClient(app).get("/api/phase3/status").status_code == 503


def test_status_route_has_no_mutation_methods() -> None:
    api = make_client()
    methods = api.get("/openapi.json").json()["paths"]["/api/phase3/status"]
    assert set(methods) == {"get"}
    assert api.post("/api/phase3/status", json={}).status_code == 405
    assert api.delete("/api/phase3/status").status_code == 405


def test_status_payload_is_detached_from_source_objects() -> None:
    shared = {"healthy": True, "nested": {"depth": 1}}
    sources = Phase3StatusSources(*((lambda: shared) for _ in NAMES))
    app = FastAPI()
    app.include_router(create_phase3_status_router(sources))
    payload = TestClient(app).get("/api/phase3/status").json()
    shared["nested"]["depth"] = 2
    assert payload["status"]["runtime_health"]["nested"]["depth"] == 1
