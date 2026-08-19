from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request


router = APIRouter(
    prefix="/api/v2/execution",
    tags=["execution-risk"],
)


@router.get("/risk-events")
def get_execution_risk_events(
    request: Request,
    symbol: str | None = None,
    event_type: str | None = None,
    start_timestamp: str | None = None,
    end_timestamp: str | None = None,
    limit: int | None = Query(
        default=None,
        ge=1,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
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

    if store is None:
        events = gate.get_risk_events()

        return {
            "status": "READY",
            "events": events,
            "count": len(events),
        }

    try:
        events = store.query_events(
            symbol=symbol,
            event_type=event_type,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "status": "READY",
        "events": events,
        "count": len(events),
    }
