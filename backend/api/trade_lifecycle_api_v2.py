from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


class SubmitTradeRequestV2(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
    )

    signal: dict[str, Any]

    order_type: str = Field(
        min_length=1,
    )


class UpdatePositionRequestV2(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
    )

    current_price: float = Field(
        gt=0,
    )


def create_trade_lifecycle_router_v2(
    *,
    service: TradeLifecycleServiceV2,
) -> APIRouter:
    if not isinstance(
        service,
        TradeLifecycleServiceV2,
    ):
        raise TypeError(
            "service debe ser "
            "TradeLifecycleServiceV2."
        )

    router = APIRouter()

    @router.get(
        "/v2/positions",
    )
    def get_active_positions() -> dict[
        str,
        object,
    ]:
        positions = (
            service.get_active_positions()
        )

        return {
            "positions": positions,
            "count": len(
                positions
            ),
        }

    @router.post(
        "/v2/trades/submit",
    )
    def submit_trade(
        request: SubmitTradeRequestV2,
    ) -> dict[str, object]:
        try:
            result = service.submit_signal(
                signal=request.signal,
                order_type=request.order_type,
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise HTTPException(
                status_code=422,
                detail=str(
                    error
                ),
            ) from error

        if (
            result.get(
                "reason"
            )
            == "position_already_open"
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "position_already_open"
                ),
            )

        return result

    @router.post(
        "/v2/positions/"
        "{position_id}/update",
    )
    def update_position(
        position_id: str,
        request: UpdatePositionRequestV2,
    ) -> dict[str, object]:
        try:
            return service.update_position(
                position_id=position_id,
                current_price=(
                    request.current_price
                ),
            )
        except ValueError as error:
            message = str(
                error
            )

            if (
                message
                == "position_id no existe."
            ):
                raise HTTPException(
                    status_code=404,
                    detail=message,
                ) from error

            raise HTTPException(
                status_code=422,
                detail=message,
            ) from error

    @router.get(
        "/v2/trades/history",
    )
    def get_trade_history(
        limit: int | None = Query(
            default=None,
            gt=0,
        ),
        symbol: str | None = Query(
            default=None,
        ),
    ) -> dict[str, object]:
        try:
            trades = (
                service.get_trade_history(
                    limit=limit,
                    symbol=symbol,
                )
            )
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail=str(
                    error
                ),
            ) from error

        return {
            "trades": trades,
            "count": len(
                trades
            ),
        }

    @router.get(
        "/v2/performance",
    )
    def get_performance() -> dict[
        str,
        object,
    ]:
        return (
            service.get_performance_metrics()
        )

    return router
