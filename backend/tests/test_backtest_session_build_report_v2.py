from backend.backtesting.backtest_report_v2 import (
    BacktestReportV2,
)
from backend.backtesting.backtest_session_v2 import (
    BacktestSessionV2,
)
from backend.services.signal_submission_target_v2 import (
    SignalSubmissionTargetV2,
)
from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)


class FakeBacktestRunner:

    def run(self, *, on_candle=None) -> int:

        candles = [
            {
                "symbol": "NQ",
                "timeframe": "5m",
                "close": 20000.0,
            },
            {
                "symbol": "NQ",
                "timeframe": "5m",
                "close": 20020.0,
            },
        ]

        for candle in candles:
            if on_candle is not None:
                on_candle(
                    candle,
                    {
                        "processed": True,
                    },
                )

        return len(candles)


class FakeStrategyRunner:

    def __init__(self) -> None:
        self.calls = 0

    def run(self, context) -> TradingDecisionV2:

        self.calls += 1

        if self.calls == 1:
            return TradingDecisionV2(
                action=TradingActionV2.BUY,
                confidence=0.90,
                reason="REPORT TEST",
            )

        return TradingDecisionV2(
            action=TradingActionV2.HOLD,
            confidence=1.0,
            reason="HOLD",
        )


class FakeLifecycle(
    SignalSubmissionTargetV2,
):

    def submit_signal(
        self,
        *,
        signal,
        order_type,
        risk_context=None,
        order_context=None,
    ):
        return {
            "accepted": True,
            "active_position_id": "POS-1",
        }

    def get_trade_history(self):
        return [
            {
                "trade_id": "T-1",
                "symbol": "NQ",
                "result": "WIN",
            },
        ]

    def get_performance_metrics(self):
        return {
            "total_trades": 1,
            "wins": 1,
            "losses": 0,
            "equity_curve": [
                17000.0,
                17100.0,
            ],
        }

    def get_active_positions(self):
        return [
            {
                "position_id": "POS-1",
                "symbol": "NQ",
                "status": "OPEN",
            },
        ]


def test_builds_consolidated_backtest_report():

    lifecycle = FakeLifecycle()

    session = BacktestSessionV2(
        backtest_runner_v2=FakeBacktestRunner(),
        strategy_runner_v2=FakeStrategyRunner(),
        signal_submission_target_v2=lifecycle,
    )

    processed = session.run()

    report = session.build_report(
        candles_processed=processed,
    )

    assert isinstance(
        report,
        BacktestReportV2,
    )

    assert report.candles_processed == 2
    assert len(report.decisions) == 2

    assert report.trade_plans == []
    assert report.signals == []
    assert report.submission_results == []
    assert report.position_updates == []

    assert report.trade_history == [
        {
            "trade_id": "T-1",
            "symbol": "NQ",
            "result": "WIN",
        },
    ]

    assert report.performance_metrics == {
        "total_trades": 1,
        "wins": 1,
        "losses": 0,
        "equity_curve": [
            17000.0,
            17100.0,
        ],
    }

    assert report.active_positions == [
        {
            "position_id": "POS-1",
            "symbol": "NQ",
            "status": "OPEN",
        },
    ]

    assert report.summary() == {
        "candles_processed": 2,
        "decisions": 2,
        "trade_plans": 0,
        "signals": 0,
        "submissions": 0,
        "position_updates": 0,
        "closed_trades": 1,
        "active_positions": 1,
    }


def test_build_report_works_without_lifecycle():

    session = BacktestSessionV2(
        backtest_runner_v2=FakeBacktestRunner(),
        strategy_runner_v2=FakeStrategyRunner(),
    )

    processed = session.run()

    report = session.build_report(
        candles_processed=processed,
    )

    assert report.trade_history == []
    assert report.performance_metrics == {}
    assert report.active_positions == []


def test_build_report_rejects_negative_candles():

    session = BacktestSessionV2(
        backtest_runner_v2=FakeBacktestRunner(),
        strategy_runner_v2=FakeStrategyRunner(),
    )

    try:
        session.build_report(
            candles_processed=-1,
        )
    except ValueError as exc:
        assert "candles_processed" in str(exc)
    else:
        raise AssertionError(
            "Se esperaba ValueError."
        )
