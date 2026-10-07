from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.beta_dashboard_api_v1 import create_beta_dashboard_router_v1
from backend.dashboard.beta_dashboard_projection_v1 import BetaDashboardProjectionV1
from backend.security.beta_access_v1 import BetaUserStoreV1


PASSWORD = "correct-horse-beta-2026"


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value


class MappingStore:
    def __init__(self, value):
        self.value = value

    def get_latest(self, **_kwargs):
        return dict(self.value) if self.value is not None else None


class HistoryStore:
    def __init__(self, values):
        self.values = values

    def get_history(self, **_kwargs):
        return [dict(value) for value in self.values]


class ReadService:
    def get_snapshot(self):
        return {
            "dashboard_status": "READY",
            "execution_mode": "PAPER",
            "runtime": {"account_id": "PRIVATE-PAPER-A", "runtime_generation": 7},
            "journal_history": [
                {
                    "trade_id": "trade-1",
                    "symbol": "MNQ",
                    "direction": "LONG",
                    "entry": 20000.0,
                    "stop_loss": 19990.0,
                    "take_profit": 20020.0,
                    "created_at": "2026-10-06T13:00:00+00:00",
                    "closed_at": "2026-10-06T14:00:00+00:00",
                    "exit_price": 20020.0,
                    "result": "TARGET_HIT",
                    "pnl": 40.0,
                    "status": "CLOSED",
                },
                {
                    "trade_id": "trade-2",
                    "symbol": "MNQ",
                    "direction": "SHORT",
                    "entry": 20010.0,
                    "stop_loss": 20020.0,
                    "take_profit": 19990.0,
                    "created_at": "2026-10-05T13:00:00+00:00",
                    "closed_at": "2026-10-05T14:00:00+00:00",
                    "exit_price": 20020.0,
                    "result": "STOPPED",
                    "pnl": -20.0,
                    "status": "CLOSED",
                },
            ],
        }


def build_client():
    clock = Clock()
    store = BetaUserStoreV1(now_provider=clock)
    admin = store.create_user(email="admin@example.com", password=PASSWORD, role="admin")
    beta = store.create_user(email="beta@example.com", password=PASSWORD)
    app = FastAPI()
    app.state.live_signal_store = MappingStore(
        {
            "signal_id": "signal-live",
            "symbol": "MNQ",
            "timeframe": "5m",
            "action": "BUY",
            "approved": True,
            "status": "ACTIVE",
            "probability": 0.84,
            "confluence": 0.88,
            "entry_price": 20000.0,
            "stop_loss": 19990.0,
            "take_profit": 20020.0,
            "reward_risk": 2.0,
            "generated_at": "2026-10-06T15:00:00+00:00",
            "market_data": {"status": "AVAILABLE"},
        }
    )
    app.state.live_analysis_store = MappingStore(None)
    duplicate = {
        "signal_id": "signal-history",
        "symbol": "MNQ",
        "timeframe": "5m",
        "action": "SELL",
        "approved": False,
        "entry_price": 20010.0,
        "stop_loss": 20020.0,
        "take_profit": 19990.0,
        "generated_at": "2026-10-05T15:00:00+00:00",
    }
    app.state.signal_history_store = HistoryStore([duplicate, duplicate])
    app.state.submit_order = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("beta read attempted execution")
    )
    app.include_router(
        create_beta_dashboard_router_v1(
            user_store=store,
            projection=BetaDashboardProjectionV1(symbol="MNQ", timeframe="5m"),
            live_data_service=ReadService(),
        )
    )
    return TestClient(app), store, clock, admin, beta, app


def login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/beta/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def test_passwords_are_one_way_and_auth_cookie_is_securely_scoped():
    client, store, *_ = build_client()
    digest = store.password_hash_for_audit("beta@example.com")
    assert PASSWORD not in digest
    assert digest.startswith("pbkdf2_sha256$600000$")
    response = client.post(
        "/api/v1/beta/auth/login",
        json={"email": "beta@example.com", "password": PASSWORD},
    )
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/api/v1/beta" in cookie
    assert PASSWORD not in response.text
    assert "password_hash" not in response.text


def test_local_username_admin_can_authenticate_without_plaintext_storage():
    store = BetaUserStoreV1()
    admin = store.create_user(email="arms_admin", password=PASSWORD, role="admin")

    session = store.authenticate(email="ARMS_ADMIN", password=PASSWORD)

    assert session.user.user_id == admin.user_id
    assert session.user.role == "admin"
    assert session.user.status == "active"
    assert PASSWORD not in store.password_hash_for_audit("arms_admin")


def test_beta_routes_require_auth_and_return_only_paper_read_models():
    client, *_ = build_client()
    assert client.get("/api/v1/beta/dashboard").status_code == 401
    login(client, "beta@example.com")
    response = client.get("/api/v1/beta/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert payload["product_state"] == "BETA"
    assert payload["paper_only"] is True
    assert payload["live"]["current_signal"] == "BUY"
    assert payload["live"]["signal"]["status"] == "ACTIVE"
    assert payload["live"]["signal"]["source_runtime_id"] != "PRIVATE-PAPER-A"
    assert payload["history"]["status"] == "AVAILABLE"
    assert len(payload["history"]["records"]) == 3
    rejected = next(
        row for row in payload["history"]["records"]
        if row["record_id"] == "signal-history"
    )
    assert rejected["direction"] == "NO_TRADE"
    assert rejected["entry"] is None
    assert payload["performance"]["cumulative_pnl"] == 20.0
    assert payload["performance"]["wins"] == 1
    assert payload["performance"]["losses"] == 1
    assert payload["performance"]["profit_factor"] == 2.0


def test_disabled_and_expired_users_fail_closed():
    client, store, clock, _admin, beta, _app = build_client()
    store.set_enabled(beta.user_id, enabled=False)
    response = client.post(
        "/api/v1/beta/auth/login",
        json={"email": beta.email, "password": PASSWORD},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "beta_user_disabled"

    expiring = store.create_user(email="expired@example.com", password=PASSWORD)
    clock.value += timedelta(days=31)
    response = client.post(
        "/api/v1/beta/auth/login",
        json={"email": expiring.email, "password": PASSWORD},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "beta_expired"


def test_admin_routes_enforce_role_and_csrf_and_manage_beta_window():
    client, store, _clock, _admin, beta, _app = build_client()
    beta_csrf = login(client, "beta@example.com")
    assert client.get("/api/v1/beta/admin/users").status_code == 403
    assert client.post(
        "/api/v1/beta/admin/users",
        headers={"X-ARMS-BETA-CSRF": beta_csrf},
        json={"email": "other@example.com", "password": PASSWORD},
    ).status_code == 403

    client.cookies.clear()
    admin_csrf = login(client, "admin@example.com")
    assert client.post(
        "/api/v1/beta/admin/users",
        json={"email": "missing-csrf@example.com", "password": PASSWORD},
    ).status_code == 403
    created = client.post(
        "/api/v1/beta/admin/users",
        headers={"X-ARMS-BETA-CSRF": admin_csrf},
        json={"email": "new@example.com", "password": PASSWORD},
    )
    assert created.status_code == 201
    assert created.json()["user"]["beta_expires_at"] is not None
    assert "password" not in created.text
    disabled = client.patch(
        f"/api/v1/beta/admin/users/{beta.user_id}/status",
        headers={"X-ARMS-BETA-CSRF": admin_csrf},
        json={"enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["user"]["status"] == "disabled"
    extended = client.post(
        f"/api/v1/beta/admin/users/{beta.user_id}/extend",
        headers={"X-ARMS-BETA-CSRF": admin_csrf},
        json={"days": 30},
    )
    assert extended.status_code == 200
    users = client.get("/api/v1/beta/admin/users").json()
    assert users["counts"]["total"] == 3
    assert users["counts"]["disabled"] == 1
    assert all("password" not in user for user in users["users"])
    assert store.get_user(beta.user_id).status == "disabled"

    initially_disabled = store.create_user(
        email="disabled-role@example.com", password=PASSWORD, role="disabled"
    )
    enabled = client.patch(
        f"/api/v1/beta/admin/users/{initially_disabled.user_id}/status",
        headers={"X-ARMS-BETA-CSRF": admin_csrf},
        json={"enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["user"]["role"] == "beta_user"
    assert enabled.json()["user"]["status"] == "active"


def test_logout_revokes_session_and_requires_csrf():
    client, *_ = build_client()
    csrf = login(client, "beta@example.com")
    assert client.post("/api/v1/beta/auth/logout").status_code == 403
    assert client.post(
        "/api/v1/beta/auth/logout", headers={"X-ARMS-BETA-CSRF": csrf}
    ).status_code == 200
    assert client.get("/api/v1/beta/dashboard").status_code == 401


def test_beta_api_exposes_no_trading_or_runtime_control_path():
    _client, _store, _clock, _admin, _beta, app = build_client()
    routes = []
    for route in app.routes:
        original = getattr(route, "original_router", None)
        routes.extend(getattr(original, "routes", ()) if original is not None else (route,))
    beta_routes = [
        route for route in routes if getattr(route, "path", "").startswith("/api/v1/beta")
    ]
    assert beta_routes
    forbidden = {
        "order", "trade/submit", "paper/enable", "live/enable",
        "risk/", "strategy/", "ninjatrader", "account/switch",
    }
    assert all(
        not any(token in route.path.lower() for token in forbidden)
        for route in beta_routes
    )
    data_paths = {"/api/v1/beta/dashboard", "/api/v1/beta/live",
                  "/api/v1/beta/history", "/api/v1/beta/performance"}
    for route in beta_routes:
        if route.path in data_paths:
            assert route.methods == {"GET"}
