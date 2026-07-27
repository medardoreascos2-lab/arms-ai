import pytest

from backend.performance.performance_score_engine_v2 import (
    PerformanceScoreEngineV2,
)


def build_engine():
    return PerformanceScoreEngineV2()


def build_dashboard(
    *,
    win_rate=60.0,
    profit_factor=1.8,
    expectancy=40.0,
    drawdown=500.0,
    maximum_drawdown=4500.0,
    daily_pnl=250.0,
    trading_blocked=False,
):
    return {
        "dashboard_status": (
            "BLOCKED"
            if trading_blocked
            else "READY"
        ),
        "account_state": {
            "daily_pnl": daily_pnl,
            "drawdown": drawdown,
            "maximum_total_drawdown": (
                maximum_drawdown
            ),
            "trading_blocked": (
                trading_blocked
            ),
            "blocking_reasons": (
                ["risk_limit_reached"]
                if trading_blocked
                else []
            ),
        },
        "analytics": {
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "net_profit": daily_pnl,
        },
    }


def test_scores_excellent_performance():
    engine = build_engine()

    result = engine.calculate(
        dashboard=build_dashboard(
            win_rate=70.0,
            profit_factor=2.5,
            expectancy=80.0,
            drawdown=300.0,
            daily_pnl=500.0,
        ),
    )

    assert result["score"] >= 90
    assert result["grade"] == "A+"
    assert result["status"] == "EXCELLENT"
    assert (
        result["recommendation"]
        == "CONTINUE_TRADING"
    )


def test_scores_good_performance():
    engine = build_engine()

    result = engine.calculate(
        dashboard=build_dashboard(
            win_rate=58.0,
            profit_factor=1.7,
            expectancy=35.0,
            drawdown=900.0,
            daily_pnl=150.0,
        ),
    )

    assert 75 <= result["score"] < 90
    assert result["grade"] in {
        "A",
        "B+",
    }
    assert result["status"] == "GOOD"


def test_penalizes_high_drawdown():
    engine = build_engine()

    result = engine.calculate(
        dashboard=build_dashboard(
            win_rate=65.0,
            profit_factor=2.0,
            expectancy=50.0,
            drawdown=4000.0,
            maximum_drawdown=4500.0,
        ),
    )

    assert result["score"] < 75
    assert (
        "high_drawdown"
        in result["penalties"]
    )


def test_blocks_score_when_account_blocked():
    engine = build_engine()

    result = engine.calculate(
        dashboard=build_dashboard(
            trading_blocked=True,
            drawdown=4500.0,
            daily_pnl=-3000.0,
        ),
    )

    assert result["score"] == 0
    assert result["grade"] == "F"
    assert result["status"] == "BLOCKED"
    assert (
        result["recommendation"]
        == "STOP_TRADING"
    )


def test_handles_empty_dashboard():
    engine = build_engine()

    result = engine.calculate(
        dashboard={
            "dashboard_status": "EMPTY",
            "account_state": None,
            "analytics": None,
        },
    )

    assert result["score"] == 0
    assert result["grade"] == "N/A"
    assert result["status"] == "NO_DATA"
    assert (
        result["recommendation"]
        == "WAIT_FOR_DATA"
    )


def test_returns_score_breakdown():
    engine = build_engine()

    result = engine.calculate(
        dashboard=build_dashboard(),
    )

    breakdown = result[
        "score_breakdown"
    ]

    assert "win_rate_score" in breakdown
    assert "profit_factor_score" in breakdown
    assert "expectancy_score" in breakdown
    assert "drawdown_score" in breakdown
    assert "daily_pnl_score" in breakdown


def test_rejects_invalid_dashboard_type():
    engine = build_engine()

    with pytest.raises(
        TypeError,
        match="dashboard",
    ):
        engine.calculate(
            dashboard=object(),
        )
