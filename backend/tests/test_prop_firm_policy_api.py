"""Read-only prop-firm policy API tests."""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.api.routers.prop_firm_policy_api_v1 import (
    create_prop_firm_policy_router,
)
from backend.prop_firms import canonical_profile_registry


NOW = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)


class MutationProbe:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def submit_order(self) -> None:
        self.calls.append("submit_order")

    def create_position(self) -> None:
        self.calls.append("create_position")

    def write_journal(self) -> None:
        self.calls.append("write_journal")


def build_client() -> tuple[TestClient, MutationProbe]:
    app = FastAPI()
    probe = MutationProbe()
    app.state.execution_service = probe
    app.state.paper_service = probe
    app.state.portfolio_service = probe
    app.state.journal_service = probe
    app.include_router(create_prop_firm_policy_router(canonical_profile_registry()))
    return TestClient(app), probe


def topstep_snapshot(account_id: str = "topstep-1") -> dict:
    instant = NOW.isoformat()
    return {
        "account_id": account_id,
        "firm_id": "topstep",
        "program_id": "trading_combine",
        "profile_version": "2026-10-03/no-dll",
        "stage": "EVALUATION",
        "account_size": "50000",
        "captured_at": instant,
        "data_source": f"runtime://paper/{account_id}",
        "simulated": True,
        "state": {
            "as_of": instant,
            "stage": "EVALUATION",
            "starting_balance": "50000",
            "current_balance": "53000",
            "current_equity": "53000",
            "realized_pnl": "3000",
            "daily_pnl": "0",
            "highest_end_of_day_balance": "53000",
            "contracts_open": 0,
            "contracts_traded": 0,
            "trading_days": 2,
            "best_day_profit": "1500",
            "total_profit": "3000",
            "withdrawals": "0",
            "prior_account_failed": False,
            "exposures": [{"instrument": "NQ", "quantity": 1}],
        },
    }


def test_router_exposes_only_four_declared_policy_operations_and_is_not_mutating():
    router = create_prop_firm_policy_router(canonical_profile_registry())
    routes = {
        (route.path, frozenset(route.methods or set()))
        for route in router.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1/prop-firms")
    }
    assert routes == {
        ("/api/v1/prop-firms/profiles", frozenset({"GET"})),
        ("/api/v1/prop-firms/profiles/resolve", frozenset({"GET"})),
        ("/api/v1/prop-firms/evaluate/account", frozenset({"POST"})),
        ("/api/v1/prop-firms/evaluate/accounts", frozenset({"POST"})),
    }
    assert all(not methods.intersection({"PUT", "PATCH", "DELETE"}) for _, methods in routes)


def test_policy_router_is_not_wired_into_the_operational_application():
    application_source = (
        Path(__file__).parents[1] / "api" / "app.py"
    ).read_text(encoding="utf-8")
    assert "prop_firm_policy_api_v1" not in application_source
    assert '\"/api/v1/prop-firms' not in application_source


def test_list_and_resolve_profiles_are_temporal_and_source_status_aware():
    client, probe = build_client()
    response = client.get(
        "/api/v1/prop-firms/profiles",
        params={"at": NOW.isoformat(), "firm_id": "topstep"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] > 0
    assert {item["firm_id"] for item in body["profiles"]} == {"topstep"}
    assert all(isinstance(item["account_size"], str) for item in body["profiles"])
    assert "50000" in {item["account_size"] for item in body["profiles"]}

    blocked = client.get(
        "/api/v1/prop-firms/profiles/resolve",
        params={
            "firm_id": "lucid",
            "program_id": "lucidpro_evaluation",
            "stage": "EVALUATION",
            "account_size": "50000",
            "at": NOW.isoformat(),
            "version": "2026-10-03",
        },
    )
    assert blocked.status_code == 409
    inspected = client.get(
        "/api/v1/prop-firms/profiles/resolve",
        params={
            "firm_id": "lucid",
            "program_id": "lucidpro_evaluation",
            "stage": "EVALUATION",
            "account_size": "50000",
            "at": NOW.isoformat(),
            "version": "2026-10-03",
            "allow_unverified": "true",
        },
    )
    assert inspected.status_code == 200
    assert inspected.json()["source_status"] == "INCOMPLETE"
    assert probe.calls == []


def test_single_account_evaluation_is_diagnostic_only_and_preserves_precision():
    client, probe = build_client()
    payload = {
        "snapshot": topstep_snapshot(),
        "require_current_sources": True,
    }
    response = client.post("/api/v1/prop-firms/evaluate/account", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["account_id"] == "topstep-1"
    assert body["account_valid"] is True
    assert body["trading_allowed_now"] is True
    assert body["execution_authorized"] is False
    assert body["snapshot_hash"]
    assert probe.calls == []


def test_multi_account_resolution_failure_isolated_and_never_authorizes_execution():
    client, probe = build_client()
    missing = topstep_snapshot("missing-1")
    missing.update({
        "firm_id": "unknown",
        "program_id": "missing",
        "profile_version": "v1",
    })
    response = client.post(
        "/api/v1/prop-firms/evaluate/accounts",
        json={"snapshots": [missing, topstep_snapshot()]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    by_id = {item["account_id"]: item for item in body["accounts"]}
    assert by_id["missing-1"]["account_valid"] is False
    assert by_id["missing-1"]["trading_allowed_now"] is False
    assert by_id["topstep-1"]["account_valid"] is True
    assert body["execution_authorized"] is False
    assert all(item["execution_authorized"] is False for item in body["accounts"])
    assert probe.calls == []


def test_payout_evaluation_and_invalid_payloads_have_zero_side_effects():
    client, probe = build_client()
    response = client.post(
        "/api/v1/prop-firms/evaluate/account",
        json={
            "snapshot": topstep_snapshot(),
            "payout_request": {"amount": "500.25"},
        },
    )
    assert response.status_code == 200
    assert response.json()["payout_evaluated"] is True
    assert response.json()["execution_authorized"] is False

    mismatch = topstep_snapshot()
    mismatch["stage"] = "FUNDED"
    rejected = client.post(
        "/api/v1/prop-firms/evaluate/account",
        json={"snapshot": mismatch},
    )
    assert rejected.status_code == 422

    extra = topstep_snapshot()
    extra["state"]["invented_balance"] = "999999"
    rejected_extra = client.post(
        "/api/v1/prop-firms/evaluate/account",
        json={"snapshot": extra},
    )
    assert rejected_extra.status_code == 422

    coerced = topstep_snapshot()
    coerced["simulated"] = "true"
    rejected_coercion = client.post(
        "/api/v1/prop-firms/evaluate/account",
        json={"snapshot": coerced},
    )
    assert rejected_coercion.status_code == 422

    floating_money = topstep_snapshot()
    floating_money["state"]["current_balance"] = 53000.25
    rejected_float = client.post(
        "/api/v1/prop-firms/evaluate/account",
        json={"snapshot": floating_money},
    )
    assert rejected_float.status_code == 422
    assert probe.calls == []
