from datetime import datetime

from pydantic import BaseModel, Field


class AIDecisionRequest(BaseModel):
    weights: dict[str, float]
    metrics: dict[str, float]


class AICopilotRequest(BaseModel):
    question: str
    weights: dict[str, float]
    metrics: dict[str, float]


class TradingCandleRequest(BaseModel):
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


class AITradingContextRequest(BaseModel):
    symbol: str = Field(
        min_length=1,
    )
    timeframe: str = Field(
        min_length=1,
    )
    candles: list[TradingCandleRequest] = Field(
        min_length=50,
    )
    account_balance: float = Field(
        gt=0,
    )
    risk_percent: float = Field(
        gt=0,
    )
    point_value: float = Field(
        gt=0,
    )
    reward_risk_ratio: float = Field(
        gt=0,
    )
