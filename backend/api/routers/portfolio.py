from fastapi import APIRouter

from backend.api.schemas.portfolio import (
    PortfolioAnalyzeRequest,
)
from backend.application.analyze_portfolio import (
    AnalyzePortfolio,
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
