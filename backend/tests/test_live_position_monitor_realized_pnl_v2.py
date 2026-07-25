import pytest

from backend.execution.break_even_engine_v2 import (
    BreakEvenEngineV2,
)
from backend.execution.partial_take_profit_engine_v2 import (
    PartialTakeProfitEngineV2,
)
from backend.execution.realized_pnl_engine_v2 import (
    RealizedPnLEngineV2,
)
from backend.execution.trailing_stop_engine_v2 import (
    TrailingStopEngineV2,
)
from backend.services.live_position_monitor_v2 import (
    LivePositionMonitorV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


class FakeTradeLifecycleService(
    TradeLifecycleServiceV2
):

    def __init__(self):
        self.position = {
            "position_id": "pos-1",
            "symbol": "NQ",
            "status": "OPEN",
            "direction": "LONG",
            "entry_price": 100.0,
            "current_price": 100.0,
            "quantity": 2.0,
            "original_quantity": 2.0,
            "stop_loss": 95.0,
            "take_profit": 120.0,
            "partial_taken": False,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
        }

    def get_active_positions(self):
        return [dict(self.position)]

    def replace_active_position(
        self,
        *,
        position,
    ):
        self.position = dict(
            position
        )

        return dict(
            self.position
        )

    def update_position(
        self,
        *,
        position_id,
        current_price,
    ):
        self.position["current_price"] = current_price

        return {
            "updated": True,
            "position": dict(self.position),
            "trade_record": None,
            "performance_metrics": None,
            "active_position_removed": False,
        }


def build_monitor():

    lifecycle = FakeTradeLifecycleService()

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        partial_take_profit_engine=(
            PartialTakeProfitEngineV2(
                trigger_profit_points=10.0,
                close_fraction=0.50,
            )
        ),
        realized_pnl_engine=(
            RealizedPnLEngineV2(
                point_value=2.0,
            )
        ),
        break_even_engine=(
            BreakEvenEngineV2(
                trigger_profit_points=5.0,
                offset_points=0.0,
            )
        ),
        trailing_stop_engine=(
            TrailingStopEngineV2(
                activation_profit_points=8.0,
                trailing_distance_points=3.0,
            )
        ),
    )

    return lifecycle, monitor


def test_realized_pnl_is_calculated_after_partial():

    _, monitor = build_monitor()

    result = monitor.process_price(
        symbol="NQ",
        current_price=110.0,
    )

    pnl = result["realized_pnl_results"][0]

    assert pnl["calculated"] is True
    assert pnl["realized_pnl"] == 20.0

    position = pnl["position"]

    assert position["realized_pnl"] == 20.0
    assert position["partial_pnl_recorded"] is True


def test_monitor_without_realized_engine():

    lifecycle = FakeTradeLifecycleService()

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        partial_take_profit_engine=None,
        realized_pnl_engine=None,
        break_even_engine=None,
        trailing_stop_engine=None,
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=110.0,
    )

    assert result["processed"] is True
    assert result["realized_pnl_results"] == []


def test_invalid_realized_engine():

    lifecycle = FakeTradeLifecycleService()

    with pytest.raises(
        TypeError,
        match="realized_pnl_engine",
    ):
        LivePositionMonitorV2(
            trade_lifecycle_service=lifecycle,
            realized_pnl_engine=object(),
        )
