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
