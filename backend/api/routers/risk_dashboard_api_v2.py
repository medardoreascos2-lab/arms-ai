from __future__ import annotations

from fastapi import APIRouter, Request

from backend.api.dashboard.risk_dashboard_api_v1 import (
    RiskDashboardAPIv1,
)
from backend.risk.risk_event_analytics_v2 import (
    RiskEventAnalyticsV2,
)


router = APIRouter(
    prefix="/api/v2/dashboard",
    tags=["risk-dashboard"],
)


risk_api = RiskDashboardAPIv1()


@router.get("/risk")
def get_risk_dashboard(
    request: Request,
) -> dict[str, object]:

    dashboard = dict(
        risk_api.get_risk_dashboard()
    )

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
