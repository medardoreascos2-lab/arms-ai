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



class PortfolioBacktestRequest(BaseModel):
    symbols: list[str] = Field(
        min_length=1,
    )
    weights: dict[str, float]
    period: str = "1y"
    initial_value: float = Field(
        default=1000.0,
        gt=0.0,
    )
    risk_free_rate: float = 0.0


class RiskAnalyticsRequest(BaseModel):
    returns: list[float] = Field(
        min_length=1,
    )
    risk_free_rate: float = 0.0



class RiskAnalyticsMarketRequest(BaseModel):
    symbols: list[str] = Field(
        min_length=1,
    )
    weights: dict[str, float]
    period: str = "1y"
    risk_free_rate: float = 0.0



class BenchmarkAnalyticsRequest(BaseModel):
    symbols: list[str] = Field(
        min_length=1,
    )
    weights: dict[str, float]
    benchmark: str = "SPY"
    period: str = "1y"
    risk_free_rate: float = 0.0



class DrawdownAnalyticsRequest(BaseModel):
    symbols: list[str] = Field(
        min_length=1,
    )
    weights: dict[str, float]
    period: str = "1y"



class RollingAnalyticsRequest(BaseModel):
    symbols: list[str] = Field(
        min_length=1,
    )
    weights: dict[str, float]
    period: str = "1y"
    window: int = Field(
        default=30,
        gt=0,
    )
    risk_free_rate: float = 0.0



class CapmAnalyticsRequest(BaseModel):
    symbols: list[str] = Field(
        min_length=1,
    )
    weights: dict[str, float]
    market: str = "SPY"
    period: str = "1y"
    risk_free_rate: float = 0.0



class FamaFrenchAnalyticsRequest(BaseModel):
    symbols: list[str] = Field(
        min_length=1,
    )
    weights: dict[str, float]
    market: str = "SPY"
    small_cap: str = "IWM"
    value: str = "IWD"
    growth: str = "IWF"
    period: str = "1y"
    risk_free_rate: float = 0.0
