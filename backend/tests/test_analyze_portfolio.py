import pytest

from backend.application.analyze_portfolio import (
    AnalyzePortfolio,
)
from backend.portfolio.portfolio_analysis_service import (
    PortfolioAnalysisService,
)


def build_inputs():
    return {
        "returns": {
            "A": [0.01, 0.02, 0.03, 0.04],
            "B": [0.02, 0.01, 0.03, 0.05],
            "C": [0.03, 0.01, 0.02, 0.04],
        },
        "volatilities": {
            "A": 0.10,
            "B": 0.20,
            "C": 0.30,
        },
        "expected_returns": {
            "A": 0.08,
            "B": 0.12,
            "C": 0.18,
        },
    }


def test_use_case_returns_analysis_payload():
    use_case = AnalyzePortfolio()

    payload = use_case.execute(
        **build_inputs(),
        risk_free_rate=0.02,
    )

    assert isinstance(payload, dict)
    assert payload["strategy"]
    assert payload["risk_level"]
    assert isinstance(
        payload["target_weights"],
        dict,
    )


def test_use_case_supports_rebalancing():
    use_case = AnalyzePortfolio()

    payload = use_case.execute(
        **build_inputs(),
        current_weights={
            "A": 50.0,
            "B": 30.0,
            "C": 20.0,
        },
        tolerance=0.5,
    )

    assert payload["rebalancing"] is not None
    assert "trades" in payload["rebalancing"]


def test_use_case_exposes_detailed_result():
    use_case = AnalyzePortfolio()

    result = use_case.execute_detailed(
        **build_inputs(),
    )

    assert result.assets == (
        "A",
        "B",
        "C",
    )
    assert result.optimization is not None


def test_use_case_accepts_injected_service():
    service = PortfolioAnalysisService()
    use_case = AnalyzePortfolio(
        service=service,
    )

    payload = use_case.execute(
        **build_inputs(),
    )

    assert payload["strategy"]


def test_use_case_rejects_invalid_service():
    with pytest.raises(
        TypeError,
        match="PortfolioAnalysisService",
    ):
        AnalyzePortfolio(
            service=object(),
        )


def test_use_case_rejects_empty_returns():
    use_case = AnalyzePortfolio()

    with pytest.raises(
        ValueError,
        match="returns",
    ):
        use_case.execute(
            returns={},
            volatilities={},
            expected_returns={},
        )


def test_use_case_is_stateless():
    use_case = AnalyzePortfolio()

    first = use_case.execute(
        **build_inputs(),
    )
    second = use_case.execute(
        **build_inputs(),
    )

    first["target_weights"]["A"] = 0.0

    assert second["target_weights"]["A"] != 0.0
