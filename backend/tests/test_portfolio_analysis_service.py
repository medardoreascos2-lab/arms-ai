import pytest

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


def test_service_returns_serializable_payload():
    service = PortfolioAnalysisService()

    payload = service.analyze(
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


def test_service_supports_rebalancing():
    service = PortfolioAnalysisService()

    payload = service.analyze(
        **build_inputs(),
        current_weights={
            "A": 50.0,
            "B": 30.0,
            "C": 20.0,
        },
    )

    assert payload["rebalancing"] is not None
    assert "trades" in payload["rebalancing"]


def test_service_allows_analysis_without_rebalancing():
    service = PortfolioAnalysisService()

    payload = service.analyze(
        **build_inputs(),
    )

    assert payload["rebalancing"] is None


def test_service_preserves_assets():
    service = PortfolioAnalysisService()

    result = service.analyze_detailed(
        **build_inputs(),
    )

    assert result.assets == (
        "A",
        "B",
        "C",
    )


def test_service_rejects_empty_returns():
    service = PortfolioAnalysisService()

    with pytest.raises(
        ValueError,
        match="returns",
    ):
        service.analyze(
            returns={},
            volatilities={},
            expected_returns={},
        )


def test_service_is_stateless():
    service = PortfolioAnalysisService()

    first = service.analyze(
        **build_inputs(),
    )
    second = service.analyze(
        **build_inputs(),
    )

    first["target_weights"]["A"] = 0.0

    assert second["target_weights"]["A"] != 0.0
