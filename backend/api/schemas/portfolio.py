from pydantic import BaseModel, Field


class PortfolioAnalyzeRequest(BaseModel):
    returns: dict[str, list[float]]
    volatilities: dict[str, float]
    expected_returns: dict[str, float]
    risk_free_rate: float = 0.0
    current_weights: dict[str, float] | None = None
    tolerance: float = Field(
        default=0.0,
        ge=0.0,
    )



class PortfolioRebalanceRequest(BaseModel):
    current_weights: dict[str, float]
    target_weights: dict[str, float]
    tolerance: float = Field(
        default=0.0,
        ge=0.0,
    )



class PortfolioSimulateRequest(BaseModel):
    initial_value: float = Field(
        gt=0.0,
    )
    mean_return: float
    volatility: float = Field(
        ge=0.0,
    )
    periods: int = Field(
        gt=0,
    )
    simulations: int = Field(
        gt=0,
    )
    seed: int | None = None


class PortfolioMarketRequest(BaseModel):
    symbols: list[str] = Field(
        min_length=1,
    )
    period: str = "1y"
    risk_free_rate: float = 0.0
    current_weights: dict[str, float] | None = None
    tolerance: float = Field(
        default=0.0,
        ge=0.0,
    )
