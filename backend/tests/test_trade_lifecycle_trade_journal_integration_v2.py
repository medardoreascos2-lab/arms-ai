from datetime import datetime

import pytest

from backend.analytics.performance_analytics_v2 import (
    PerformanceAnalyticsV2,
)
from backend.analytics.trade_history_manager_v2 import (
    TradeHistoryManagerV2,
)
from backend.execution.execution_manager_v2 import (
    ExecutionManagerV2,
)
from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)
from backend.execution.position_manager_v2 import (
    PositionManagerV2,
)
from backend.journal.trade_journal_v2 import (
    TradeJournalV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


def build_journal() -> TradeJournalV2:
    return TradeJournalV2()


def build_service(
    *,
    trade_journal_v2=None,
) -> TradeLifecycleServiceV2:
    return TradeLifecycleServiceV2(
        execution_manager=(
            ExecutionManagerV2(
                execution_mode="PAPER",
                maximum_contracts=20,
            )
        ),
        paper_execution_engine=(
            PaperExecutionEngineV2(
                fill_market_orders_immediately=True,
                slippage_points=0.25,
            )
        ),
        position_manager=(
            PositionManagerV2(
                point_value=2.0,
            )
        ),
        trade_history_manager=(
            TradeHistoryManagerV2()
        ),
        performance_analytics=(
            PerformanceAnalyticsV2(
                risk_free_rate=0.0,
                trading_days_per_year=252,
            )
        ),
        starting_balance=17000.0,
        risk_manager_v2=None,
        order_validation_engine_v2=None,
        exposure_manager_v2=None,
        portfolio_risk_engine_v2=None,
        portfolio_manager_v2=None,
        trade_journal_v2=trade_journal_v2,
    )


def build_signal() -> dict[str, object]:
    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 90.0,
        "take_profit": 120.0,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
    }


def test_accepts_none_trade_journal():
    service = build_service(
        trade_journal_v2=None,
    )

    assert service.trade_journal_v2 is None


def test_accepts_valid_trade_journal():
    journal = build_journal()

    service = build_service(
        trade_journal_v2=journal,
    )

    assert service.trade_journal_v2 is journal


def test_rejects_invalid_trade_journal():
    with pytest.raises(
        TypeError,
        match="trade_journal_v2",
    ):
        build_service(
            trade_journal_v2=object(),
        )


def test_submit_signal_registers_open_trade():
    journal = build_journal()

    service = build_service(
        trade_journal_v2=journal,
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
    )

    assert result["accepted"] is True

    trades = journal.get_open_trades()

    assert len(trades) == 1

    trade = trades[0]

    assert (
        trade["position_id"]
        == result["active_position_id"]
    )

    assert trade["symbol"] == "NQ"
    assert trade["direction"] == "LONG"
    assert trade["quantity"] == 2.0
    assert trade["status"] == "OPEN"

    assert isinstance(
        trade["entry_time"],
        datetime,
    )


def test_submit_signal_returns_trade_journal_summary():
    journal = build_journal()

    service = build_service(
        trade_journal_v2=journal,
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
    )

    assert result["accepted"] is True

    assert (
        result["trade_journal_summary"][
            "open_trades"
        ]
        == 1
    )

    assert (
        result["trade_journal_summary"][
            "closed_trades"
        ]
        == 0
    )


def test_without_trade_journal_returns_none_summary():
    service = build_service(
        trade_journal_v2=None,
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
    )

    assert result["accepted"] is True

    assert (
        result["trade_journal_summary"]
        is None
    )


def test_blocked_signal_does_not_register_trade():
    journal = build_journal()

    service = build_service(
        trade_journal_v2=journal,
    )

    signal = build_signal()

    signal.update(
        {
            "approved": False,
            "status": "BLOCKED",
            "decision": "DO_NOT_SEND",
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "contracts": 0,
        }
    )

    result = service.submit_signal(
        signal=signal,
        order_type="MARKET",
    )

    assert result["accepted"] is False
    assert journal.get_open_trades() == []

    assert (
        result["trade_journal_summary"][
            "open_trades"
        ]
        == 0
    )
