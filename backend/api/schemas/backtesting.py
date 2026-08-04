from __future__ import annotations

from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)


class BacktestingCandleRequest(BaseModel):
    """
    Vela histórica recibida por la API de Backtesting V2.
    """

    symbol: str = Field(
        min_length=1,
    )

    timeframe: str = Field(
        min_length=1,
    )

    timestamp: datetime

    open: float
    high: float
    low: float
    close: float

    volume: float = Field(
        ge=0.0,
    )

    @model_validator(
        mode="after",
    )
    def validate_ohlc(
        self,
    ) -> "BacktestingCandleRequest":

        highest_body_value = max(
            self.open,
            self.close,
        )

        lowest_body_value = min(
            self.open,
            self.close,
        )

        if self.high < highest_body_value:
            raise ValueError(
                "high debe ser mayor o igual "
                "que open y close."
            )

        if self.low > lowest_body_value:
            raise ValueError(
                "low debe ser menor o igual "
                "que open y close."
            )

        if self.high < self.low:
            raise ValueError(
                "high no puede ser menor que low."
            )

        return self


class BacktestingRunRequest(BaseModel):
    """
    Solicitud para ejecutar un backtest desde candles JSON.
    """

    candles: list[
        BacktestingCandleRequest
    ] = Field(
        min_length=1,
    )

    output_directory: str = Field(
        default="reports/backtesting",
        min_length=1,
    )
