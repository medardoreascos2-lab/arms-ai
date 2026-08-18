from types import SimpleNamespace

from backend.services.live_position_monitor_v2 import (
    LivePositionMonitorV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


class FakeJournal:

    def __init__(self):
        self.point_value = None

        self.trade = SimpleNamespace(
            trade_id="trade-pos-1",
            symbol="NQ",
            direction="LONG",
            entry=100.0,
            contracts=1,
            pnl=0.0,
        )

    def get_open_trades(self):
        return [self.trade]

    def close_trade(
        self,
        *,
        trade_id,
        exit_price,
        point_value,
        pnl,
        result,
        exit_reason=None,
    ):
        self.point_value = point_value

        calculated_pnl = (
            (exit_price - self.trade.entry)
            * self.trade.contracts
            * point_value
        )

        self.trade.pnl = (
            pnl
            if pnl != 0.0
            else calculated_pnl
        )


class FakeLifecycle(
    TradeLifecycleServiceV2
):

    def __init__(
        self,
        *,
        symbol,
    ):
        self.symbol = symbol
        self.trade_journal_v2 = FakeJournal()

        self.trade_journal_v2.trade.symbol = symbol

        self.position = {
            "position_id": "pos-1",
            "symbol": symbol,
            "status": "OPEN",
            "direction": "LONG",
            "entry_price": 100.0,
            "current_price": 100.0,
            "quantity": 1.0,
            "stop_loss": 95.0,
            "take_profit": 110.0,
            "realized_pnl": 0.0,
        }

    def get_active_positions(self):
        return [dict(self.position)]

    def update_position(
        self,
        *,
        position_id,
        current_price,
    ):
        updated = dict(self.position)

        updated["current_price"] = (
            current_price
        )

        if current_price >= 110.0:
            updated["status"] = "CLOSED"
            updated["close_reason"] = (
                "TAKE_PROFIT"
            )
            updated["exit_price"] = (
                current_price
            )

        self.position = updated

        return {
            "updated": True,
            "position": dict(updated),
            "performance_metrics": None,
        }


def run_close(symbol):

    lifecycle = FakeLifecycle(
        symbol=symbol,
    )

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
    )

    result = monitor.process_price(
        symbol=symbol,
        current_price=110.0,
    )

    return (
        lifecycle,
        result,
    )


def test_nq_resolves_20_dollars_per_point():

    lifecycle, result = run_close(
        "NQ"
    )

    assert result["closed_positions"] == 1

    assert (
        lifecycle.trade_journal_v2
        .point_value
        == 20.0
    )

    assert (
        lifecycle.trade_journal_v2
        .trade.pnl
        == 200.0
    )


def test_mnq_resolves_2_dollars_per_point():

    lifecycle, result = run_close(
        "MNQ"
    )

    assert result["closed_positions"] == 1

    assert (
        lifecycle.trade_journal_v2
        .point_value
        == 2.0
    )

    assert (
        lifecycle.trade_journal_v2
        .trade.pnl
        == 20.0
    )
