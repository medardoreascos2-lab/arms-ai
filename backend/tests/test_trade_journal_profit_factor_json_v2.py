import json

from backend.analytics.trade_journal_analytics_v2 import (
    TradeJournalAnalyticsV2,
)


def test_profit_factor_is_none_when_there_are_no_losses():
    analytics = TradeJournalAnalyticsV2()

    result = analytics.calculate(
        trades=[
            {
                "status": "CLOSED",
                "realized_pnl": 39.0,
                "duration_seconds": 60.0,
            },
        ],
    )

    assert result["total_trades"] == 1
    assert result["gross_profit"] == 39.0
    assert result["gross_loss"] == 0
    assert result["profit_factor"] is None

    serialized = json.dumps(
        result,
        allow_nan=False,
    )

    assert '"profit_factor": null' in serialized


def test_profit_factor_is_zero_without_closed_trades():
    analytics = TradeJournalAnalyticsV2()

    result = analytics.calculate(
        trades=[],
    )

    assert result["total_trades"] == 0
    assert result["profit_factor"] == 0.0

    json.dumps(
        result,
        allow_nan=False,
    )


def test_profit_factor_calculates_normally_with_losses():
    analytics = TradeJournalAnalyticsV2()

    result = analytics.calculate(
        trades=[
            {
                "status": "CLOSED",
                "realized_pnl": 100.0,
                "duration_seconds": 60.0,
            },
            {
                "status": "CLOSED",
                "realized_pnl": -50.0,
                "duration_seconds": 60.0,
            },
        ],
    )

    assert result["profit_factor"] == 2.0

    json.dumps(
        result,
        allow_nan=False,
    )
