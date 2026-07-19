from fastapi import APIRouter

from backend.api.schemas.portfolio import (
    PortfolioAnalyzeRequest,
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
