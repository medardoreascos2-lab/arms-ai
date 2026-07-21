import numpy as np

from fastapi import APIRouter

from backend.api.schemas.portfolio import (
    BenchmarkAnalyticsRequest,
    DrawdownAnalyticsRequest,
    PortfolioAnalyzeRequest,
    PortfolioBacktestRequest,
    RiskAnalyticsRequest,
    RiskAnalyticsMarketRequest,
    RollingAnalyticsRequest,
    PortfolioMarketRequest,
    PortfolioRebalanceRequest,
    PortfolioSimulateRequest,
)
from backend.application.analyze_portfolio import (
    AnalyzePortfolio,
)
from backend.application.optimize_portfolio import (
    OptimizePortfolio,
)
from backend.application.rebalance_portfolio import (
    RebalancePortfolio,
)
from backend.application.simulate_portfolio import (
    SimulatePortfolio,
)
from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)
from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)
from backend.portfolio.portfolio_backtest import (
    PortfolioBacktest,
)
from backend.portfolio.benchmark_analytics import (
    BenchmarkAnalytics,
)
from backend.portfolio.drawdown_analytics import (
    DrawdownAnalytics,
)
from backend.portfolio.rolling_analytics import (
    RollingAnalytics,
)
from backend.portfolio.risk_analytics import (
    RiskAnalytics,
)
from backend.portfolio.efficient_frontier import (
    EfficientFrontier,
)
from backend.services.market_data import (
    download_prices,
)
from backend.services.market_data_analysis import (
    build_portfolio_inputs_from_prices,
)


router = APIRouter(
    prefix="/portfolio",
    tags=["portfolio"],
)


@router.post("/analyze")
def analyze_portfolio(
    request: PortfolioAnalyzeRequest,
) -> dict:
    use_case = AnalyzePortfolio()

    return use_case.execute(
        returns=request.returns,
        volatilities=request.volatilities,
        expected_returns=request.expected_returns,
        risk_free_rate=request.risk_free_rate,
        current_weights=request.current_weights,
        tolerance=request.tolerance,
    )



@router.post("/optimize")
def optimize_portfolio(
    request: PortfolioAnalyzeRequest,
) -> dict:
    correlation_matrix = (
        PortfolioCorrelationMatrix.from_returns(
            request.returns
        )
    )

    covariance_matrix = (
        PortfolioCovarianceMatrix.from_inputs(
            volatilities=request.volatilities,
            correlation_matrix=correlation_matrix,
        )
    )

    report = OptimizePortfolio().execute(
        covariance_matrix=covariance_matrix,
        expected_returns=request.expected_returns,
        risk_free_rate=request.risk_free_rate,
    )

    return {
        "assets": list(
            report.assets
        ),
        "selected_strategy": (
            report.selected_strategy
        ),
        "minimum_variance": {
            "weights": dict(
                report.minimum_variance.weights
            ),
            "portfolio_variance": (
                report.minimum_variance
                .portfolio_variance
            ),
            "portfolio_volatility": (
                report.minimum_variance
                .portfolio_volatility
            ),
        },
        "maximum_sharpe": {
            "weights": dict(
                report.maximum_sharpe.weights
            ),
            "expected_return": (
                report.maximum_sharpe
                .expected_return
            ),
            "portfolio_volatility": (
                report.maximum_sharpe
                .portfolio_volatility
            ),
            "excess_return": (
                report.maximum_sharpe
                .excess_return
            ),
            "sharpe_ratio": (
                report.maximum_sharpe
                .sharpe_ratio
            ),
            "risk_free_rate": (
                report.maximum_sharpe
                .risk_free_rate
            ),
        },
        "risk_parity": {
            "weights": dict(
                report.risk_parity.weights
            ),
            "risk_contributions": dict(
                report.risk_parity
                .risk_contributions
            ),
            "portfolio_variance": (
                report.risk_parity
                .portfolio_variance
            ),
            "portfolio_volatility": (
                report.risk_parity
                .portfolio_volatility
            ),
        },
    }



@router.post("/rebalance")
def rebalance_portfolio(
    request: PortfolioRebalanceRequest,
) -> dict:
    report = RebalancePortfolio().execute(
        current_weights=request.current_weights,
        target_weights=request.target_weights,
        tolerance=request.tolerance,
    )

    return {
        "assets": list(
            report.assets
        ),
        "current_weights": dict(
            report.current_weights
        ),
        "target_weights": dict(
            report.target_weights
        ),
        "trades": dict(
            report.trades
        ),
        "turnover": report.turnover,
        "overweight_assets": list(
            report.overweight_assets
        ),
        "underweight_assets": list(
            report.underweight_assets
        ),
        "tolerance": report.tolerance,
    }



@router.post("/simulate")
def simulate_portfolio(
    request: PortfolioSimulateRequest,
) -> dict:
    result = SimulatePortfolio().execute(
        initial_value=request.initial_value,
        mean_return=request.mean_return,
        volatility=request.volatility,
        periods=request.periods,
        simulations=request.simulations,
        seed=request.seed,
    )

    return {
        "initial_value": result.initial_value,
        "mean_return": result.mean_return,
        "volatility": result.volatility,
        "periods": result.periods,
        "simulations": result.simulations,
        "seed": result.seed,
        "final_values": list(
            result.final_values
        ),
        "mean_final_value": (
            result.mean_final_value
        ),
        "median_final_value": (
            result.median_final_value
        ),
        "minimum_final_value": (
            result.minimum_final_value
        ),
        "maximum_final_value": (
            result.maximum_final_value
        ),
        "percentile_5": result.percentile_5,
        "percentile_95": result.percentile_95,
        "probability_of_loss": (
            result.probability_of_loss
        ),
    }



@router.post("/from-market")
def analyze_portfolio_from_market(
    request: PortfolioMarketRequest,
) -> dict:
    prices = download_prices(
        request.symbols,
        request.period,
    )

    inputs = (
        build_portfolio_inputs_from_prices(
            prices
        )
    )

    return AnalyzePortfolio().execute(
        returns=inputs["returns"],
        volatilities=inputs["volatilities"],
        expected_returns=inputs[
            "expected_returns"
        ],
        risk_free_rate=request.risk_free_rate,
        current_weights=request.current_weights,
        tolerance=request.tolerance,
    )



@router.post("/efficient-frontier")
def generate_efficient_frontier(
    request: PortfolioAnalyzeRequest,
) -> list[dict[str, object]]:
    assets = tuple(
        request.expected_returns
    )

    returns_matrix = np.array(
        [
            request.returns[asset]
            for asset in assets
        ],
        dtype=float,
    )

    correlation_matrix = np.corrcoef(
        returns_matrix
    )

    volatilities = np.array(
        [
            request.volatilities[asset]
            for asset in assets
        ],
        dtype=float,
    )

    covariance_matrix = (
        np.outer(
            volatilities,
            volatilities,
        )
        * correlation_matrix
    )

    return EfficientFrontier.generate(
        covariance_matrix=covariance_matrix,
        expected_returns=(
            request.expected_returns
        ),
        portfolios=1000,
        seed=42,
    )



@router.post("/backtest")
def backtest_portfolio(
    request: PortfolioBacktestRequest,
) -> dict[str, object]:
    prices = download_prices(
        request.symbols,
        request.period,
    )

    return PortfolioBacktest().run(
        prices=prices,
        weights=request.weights,
        initial_value=request.initial_value,
        risk_free_rate=request.risk_free_rate,
    )


@router.post("/risk-analytics")
def risk_analytics(
    request: RiskAnalyticsRequest,
) -> dict[str, float]:
    return RiskAnalytics().calculate(
        returns=request.returns,
        risk_free_rate=request.risk_free_rate,
    )



@router.post("/risk-analytics-from-market")
def risk_analytics_from_market(
    request: RiskAnalyticsMarketRequest,
) -> dict[str, float]:
    prices = download_prices(
        request.symbols,
        request.period,
    )

    normalized_weights = {
        symbol: float(weight)
        for symbol, weight
        in request.weights.items()
    }

    weight_sum = sum(
        normalized_weights.values()
    )

    if abs(weight_sum - 1.0) > 1e-9:
        raise ValueError(
            "weights debe sumar 1.0."
        )

    missing_assets = (
        set(normalized_weights)
        - set(prices.columns)
    )

    if missing_assets:
        raise ValueError(
            "prices no contiene todos los activos "
            "definidos en weights."
        )

    returns_frame = (
        prices[
            list(normalized_weights)
        ]
        .astype(float)
        .pct_change()
        .dropna(how="any")
    )

    if returns_frame.empty:
        raise ValueError(
            "No fue posible calcular retornos."
        )

    portfolio_returns = (
        returns_frame.mul(
            normalized_weights,
            axis="columns",
        )
        .sum(axis=1)
        .tolist()
    )

    return RiskAnalytics().calculate(
        returns=[
            float(value)
            for value in portfolio_returns
        ],
        risk_free_rate=(
            request.risk_free_rate
        ),
    )



@router.post("/benchmark-analytics")
def benchmark_analytics_from_market(
    request: BenchmarkAnalyticsRequest,
) -> dict[str, object]:
    symbols = [
        *request.symbols,
        request.benchmark.strip().upper(),
    ]

    prices = download_prices(
        symbols,
        request.period,
    )

    normalized_weights = {
        symbol.strip().upper(): float(weight)
        for symbol, weight
        in request.weights.items()
    }

    weight_sum = sum(
        normalized_weights.values()
    )

    if abs(weight_sum - 1.0) > 1e-9:
        raise ValueError(
            "weights debe sumar 1.0."
        )

    benchmark_symbol = (
        request.benchmark
        .strip()
        .upper()
    )

    required_assets = (
        set(normalized_weights)
        | {benchmark_symbol}
    )

    missing_assets = (
        required_assets
        - set(prices.columns)
    )

    if missing_assets:
        raise ValueError(
            "prices no contiene todos los activos requeridos."
        )

    returns_frame = (
        prices[
            list(normalized_weights)
            + [benchmark_symbol]
        ]
        .astype(float)
        .pct_change()
        .dropna(how="any")
    )

    if returns_frame.empty:
        raise ValueError(
            "No fue posible calcular retornos."
        )

    portfolio_returns = (
        returns_frame[
            list(normalized_weights)
        ]
        .mul(
            normalized_weights,
            axis="columns",
        )
        .sum(axis=1)
    )

    benchmark_returns = (
        returns_frame[
            benchmark_symbol
        ]
    )

    return BenchmarkAnalytics().calculate(
        portfolio_returns=[
            float(value)
            for value in portfolio_returns.tolist()
        ],
        benchmark_returns=[
            float(value)
            for value in benchmark_returns.tolist()
        ],
        risk_free_rate=(
            request.risk_free_rate
        ),
    )



@router.post("/drawdown-analytics")
def drawdown_analytics_from_market(
    request: DrawdownAnalyticsRequest,
) -> dict[str, object]:
    prices = download_prices(
        request.symbols,
        request.period,
    )

    normalized_weights = {
        symbol.strip().upper(): float(weight)
        for symbol, weight
        in request.weights.items()
    }

    weight_sum = sum(
        normalized_weights.values()
    )

    if abs(weight_sum - 1.0) > 1e-9:
        raise ValueError(
            "weights debe sumar 1.0."
        )

    missing_assets = (
        set(normalized_weights)
        - set(prices.columns)
    )

    if missing_assets:
        raise ValueError(
            "prices no contiene todos los activos "
            "definidos en weights."
        )

    returns_frame = (
        prices[
            list(normalized_weights)
        ]
        .astype(float)
        .pct_change()
        .dropna(how="any")
    )

    if returns_frame.empty:
        raise ValueError(
            "No fue posible calcular retornos."
        )

    portfolio_returns = (
        returns_frame
        .mul(
            normalized_weights,
            axis="columns",
        )
        .sum(axis=1)
        .tolist()
    )

    return DrawdownAnalytics().calculate(
        returns=[
            float(value)
            for value in portfolio_returns
        ],
    )



@router.post("/rolling-analytics")
def rolling_analytics_from_market(
    request: RollingAnalyticsRequest,
) -> dict[str, list[float]]:
    prices = download_prices(
        request.symbols,
        request.period,
    )

    normalized_weights = {
        symbol.strip().upper(): float(weight)
        for symbol, weight
        in request.weights.items()
    }

    weight_sum = sum(
        normalized_weights.values()
    )

    if abs(weight_sum - 1.0) > 1e-9:
        raise ValueError(
            "weights debe sumar 1.0."
        )

    missing_assets = (
        set(normalized_weights)
        - set(prices.columns)
    )

    if missing_assets:
        raise ValueError(
            "prices no contiene todos los activos "
            "definidos en weights."
        )

    returns_frame = (
        prices[
            list(normalized_weights)
        ]
        .astype(float)
        .pct_change()
        .dropna(how="any")
    )

    if returns_frame.empty:
        raise ValueError(
            "No fue posible calcular retornos."
        )

    portfolio_returns = (
        returns_frame
        .mul(
            normalized_weights,
            axis="columns",
        )
        .sum(axis=1)
        .tolist()
    )

    return RollingAnalytics().calculate(
        returns=[
            float(value)
            for value in portfolio_returns
        ],
        window=request.window,
        risk_free_rate=request.risk_free_rate,
    )
