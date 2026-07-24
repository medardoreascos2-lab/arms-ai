import pytest

from backend.execution.break_even_engine_v2 import (
    BreakEvenEngineV2,
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
            "stop_loss": 95.0,
            "take_profit": 110.0,
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


def test_break_even_is_applied_before_position_update():

    lifecycle = FakeTradeLifecycleService()

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        break_even_engine=BreakEvenEngineV2(
            trigger_profit_points=5.0,
            offset_points=0.0,
        ),
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=105.0,
    )

    assert result["processed"] is True
    assert result["matched_positions"] == 1

    updated = result["updated_positions"][0]

    assert (
        updated["position"]["stop_loss"]
        == 100.0
    )


def test_break_even_waits_until_trigger():

    lifecycle = FakeTradeLifecycleService()

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        break_even_engine=BreakEvenEngineV2(
            trigger_profit_points=5.0,
            offset_points=0.0,
        ),
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=104.5,
    )

    updated = result["updated_positions"][0]

    assert (
        updated["position"]["stop_loss"]
        == 95.0
    )


def test_monitor_without_break_even_engine():

    lifecycle = FakeTradeLifecycleService()

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        break_even_engine=None,
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=105.0,
    )

    assert result["processed"] is True


def test_invalid_break_even_engine():

    lifecycle = FakeTradeLifecycleService()

    with pytest.raises(
        TypeError,
        match="break_even_engine",
    ):
        LivePositionMonitorV2(
            trade_lifecycle_service=lifecycle,
            break_even_engine=object(),
        )
