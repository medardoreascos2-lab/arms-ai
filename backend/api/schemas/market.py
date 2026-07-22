from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)


class MarketWebhookRequest(BaseModel):
    symbol: str = Field(
        min_length=1,
    )
    timeframe: str = Field(
        min_length=1,
    )
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(
        ge=0,
    )
    timestamp: datetime

    @model_validator(
        mode="after"
    )
    def validate_ohlc(
        self,
    ) -> "MarketWebhookRequest":
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


class LiveMarketAnalysisRequest(BaseModel):
    symbol: str = Field(
        min_length=1,
    )
    timeframe: str = Field(
        min_length=1,
    )
    candle_limit: int = Field(
        ge=50,
        le=500,
    )
    account_balance: float = Field(
        gt=0,
    )
    risk_percent: float = Field(
        gt=0,
        le=100,
    )
    point_value: float = Field(
        gt=0,
    )
    reward_risk_ratio: float = Field(
        gt=0,
    )
