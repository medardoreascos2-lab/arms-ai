from __future__ import annotations

from fastapi import APIRouter, Request

from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)
from backend.risk.risk_event_analytics_v2 import (
    RiskEventAnalyticsV2,
)


router = APIRouter(
    prefix="/api/v2/dashboard",
    tags=["risk-dashboard"],
)


def _get_manager(
    request: Request,
) -> AccountConfigManagerV2:

    manager = getattr(
        request.app.state,
        "account_config_manager_v2",
        None,
    )

    if not isinstance(
        manager,
        AccountConfigManagerV2,
    ):
        raise RuntimeError(
            "AccountConfigManagerV2 runtime "
            "no disponible."
        )

    return manager


@router.get("/risk")
def get_risk_dashboard(
    request: Request,
) -> dict[str, object]:

    manager = _get_manager(request)
    profile = manager.get_active_account()

    balance = float(profile.account_size)
    risk_percent = float(profile.risk_percent)

    dashboard: dict[str, object] = {
        "account":
            manager.get_active_account_name(),
        "balance":
            balance,
        "risk_percent":
            risk_percent,
        "risk_per_trade":
            balance * (risk_percent / 100.0),
        "daily_loss_limit":
            profile.daily_loss_limit,
        "max_drawdown":
            profile.max_drawdown,
        "status":
            "TRADING ENABLED",
    }

    lifecycle = getattr(
        request.app.state,
        "trade_lifecycle_service_v2",
        None,
    )

    events: list[dict[str, object]] = []

    if lifecycle is not None:

        gate = getattr(
            lifecycle,
            "execution_risk_gate_v1",
            None,
        )

        if gate is not None:

            logger = getattr(
                gate,
                "logger",
                None,
            )

            store = getattr(
                logger,
                "store",
                None,
            )

            if store is not None:
                events = store.query_events()
            else:
                events = gate.get_risk_events()

    dashboard["event_analytics"] = (
        RiskEventAnalyticsV2().summarize(
            events
        )
    )

    return dashboard
