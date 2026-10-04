"""F111A: financial GET routes are admin-gated and return immutable read data."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.financial_intelligence_api_v1 import (
    FinancialReadModel, SECTIONS, create_financial_intelligence_router_v1,
)
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


def test_financial_routes_are_get_only_and_fail_closed_without_admin_token():
    app = FastAPI()
    app.state.admin_authorization_v2 = AdminAuthorizationV2(token="synthetic-test-token")
    model = FinancialReadModel.unavailable()
    router = create_financial_intelligence_router_v1(model)
    app.include_router(router)
    assert len(router.routes) == len(SECTIONS)
    assert all(route.methods == {"GET"} for route in router.routes)
    client = TestClient(app)
    for section in SECTIONS:
        path = f"/api/v1/financial/{section}"
        assert client.get(path).status_code == 401
        response = client.get(path, headers={"X-ARMS-ADMIN-TOKEN": "synthetic-test-token"})
        assert response.status_code == 200
        assert response.json() == {"status": "UNKNOWN", "reason": "NO_SOURCE_CONNECTED"}
        assert response.headers["cache-control"] == "no-store"
        assert client.post(path, headers={"X-ARMS-ADMIN-TOKEN": "synthetic-test-token"}).status_code == 405
    assert model.get("portfolio")["status"] == "UNKNOWN"


def test_query_parameters_cannot_select_another_section():
    app = FastAPI()
    app.state.admin_authorization_v2 = AdminAuthorizationV2(token="synthetic-test-token")
    payloads = {name: {"status": "UNKNOWN", "section": name} for name in SECTIONS}
    app.include_router(create_financial_intelligence_router_v1(FinancialReadModel(payloads)))
    client = TestClient(app)
    response = client.get(
        "/api/v1/financial/portfolio?section_name=shadow-medar",
        headers={"X-ARMS-ADMIN-TOKEN": "synthetic-test-token"},
    )
    assert response.json()["section"] == "portfolio"


def test_read_model_response_cannot_be_changed_by_mutating_supplied_payload():
    payloads = {name: {"status": "UNKNOWN", "nested": {"value": 1}} for name in SECTIONS}
    model = FinancialReadModel(payloads)
    payloads["portfolio"]["nested"]["value"] = 2
    model.sections["portfolio"]["nested"]["value"] = 3
    assert model.get("portfolio")["nested"]["value"] == 1
