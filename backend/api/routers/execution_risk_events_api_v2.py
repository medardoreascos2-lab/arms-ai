from __future__ import annotations

from fastapi import APIRouter, Request


router = APIRouter(
    prefix="/api/v2/execution",
    tags=["execution-risk"],
)


@router.get("/risk-events")
def get_execution_risk_events(
    request: Request,
) -> dict[str, object]:
    lifecycle = getattr(
        request.app.state,
        "trade_lifecycle_service_v2",
        None,
    )

    if lifecycle is None:
        return {
            "status": "UNAVAILABLE",
            "events": [],
            "count": 0,
        }

    gate = getattr(
        lifecycle,
        "execution_risk_gate_v1",
        None,
    )

    if gate is None:
        return {
            "status": "UNAVAILABLE",
            "events": [],
            "count": 0,
        }

    events = gate.get_risk_events()

    return {
        "status": "READY",
        "events": events,
        "count": len(events),
    }
