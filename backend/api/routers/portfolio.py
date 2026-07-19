from fastapi import APIRouter

from backend.api.schemas.portfolio import (
    PortfolioAnalyzeRequest,
)
from backend.application.analyze_portfolio import (
    AnalyzePortfolio,
)
from backend.application.optimize_portfolio import (
    OptimizePortfolio,
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
