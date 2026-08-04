from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
)

from backend.api.schemas.backtesting import (
    BacktestingRunRequest,
)
from backend.models.candle import Candle


class BacktestingUnavailableOrchestratorV2:
    """
    Dependencia segura utilizada cuando el backtesting
    todavía no fue configurado en la aplicación.
    """

    def run(
        self,
        *,
        candles,
        output_directory,
    ):
        raise HTTPException(
            status_code=503,
            detail="backtesting_orchestrator_not_configured",
        )


def create_backtesting_router_v2(
    *,
    orchestrator,
) -> APIRouter:
    """
    Crea el router REST de Backtesting V2.
    """

    if not callable(
        getattr(
            orchestrator,
            "run",
            None,
        )
    ):
        raise TypeError(
            "orchestrator debe implementar run()."
        )

    router = APIRouter(
        prefix="/api/v2/backtesting",
        tags=["backtesting-v2"],
    )

    @router.post(
        "/run",
    )
    def run_backtesting(
        request: BacktestingRunRequest,
    ) -> dict:

        try:
            candles = [
                Candle(
                    symbol=candle.symbol,
                    timeframe=candle.timeframe,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                    timestamp=candle.timestamp,
                )
                for candle in request.candles
            ]

            result = orchestrator.run(
                candles=candles,
                output_directory=(
                    request.output_directory
                ),
            )

            to_dict = getattr(
                result,
                "to_dict",
                None,
            )

            if not callable(to_dict):
                raise TypeError(
                    "orchestrator.run() debe devolver "
                    "un resultado con to_dict()."
                )

            payload = to_dict()

            if not isinstance(
                payload,
                dict,
            ):
                raise TypeError(
                    "result.to_dict() debe devolver dict."
                )

            return payload

        except HTTPException:
            raise

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=(
                    "backtesting_execution_failed"
                ),
            ) from exc

    return router
