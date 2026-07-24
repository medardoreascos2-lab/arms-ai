import pytest

from backend.execution.break_even_engine_v2 import (
    BreakEvenEngineV2,
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
    def __init__(
        self,
    ) -> None:
        self.position = {
            "position_id": "pos-1",
            "symbol": "NQ",
            "status": "OPEN",
            "direction": "LONG",
            "entry_price": 100.0,
            "current_price": 100.0,
            "stop_loss": 95.0,
            "take_profit": 120.0,
        }

    def get_active_positions(
        self,
    ):
        return [
            dict(
                self.position
            )
        ]

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
        self.position[
            "current_price"
        ] = current_price

        return {
            "updated": True,
            "position": dict(
                self.position
            ),
            "trade_record": None,
            "performance_metrics": None,
            "active_position_removed": False,
        }


def test_trailing_stop_is_applied_after_break_even():
    lifecycle = (
        FakeTradeLifecycleService()
    )

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        break_even_engine=(
            BreakEvenEngineV2(
                trigger_profit_points=5.0,
                offset_points=0.0,
            )
        ),
        trailing_stop_engine=(
            TrailingStopEngineV2(
                activation_profit_points=5.0,
                trailing_distance_points=3.0,
            )
        ),
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=108.0,
    )

    assert result["processed"] is True
    assert result["matched_positions"] == 1

    updated = result[
        "updated_positions"
    ][0]

    assert (
        updated["position"][
            "stop_loss"
        ]
        == 105.0
    )

    assert len(
        result["trailing_stop_results"]
    ) == 1

    assert (
        result["trailing_stop_results"][0][
            "status"
        ]
        == "TRAILING_ACTIVE"
    )


def test_trailing_stop_waits_before_activation():
    lifecycle = (
        FakeTradeLifecycleService()
    )

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
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

    result = monitor.process_price(
        symbol="NQ",
        current_price=105.0,
    )

    updated = result[
        "updated_positions"
    ][0]

    assert (
        updated["position"][
            "stop_loss"
        ]
        == 100.0
    )

    assert (
        result["trailing_stop_results"][0][
            "status"
        ]
        == "WAITING"
    )


def test_trailing_stop_does_not_move_stop_backward():
    lifecycle = (
        FakeTradeLifecycleService()
    )

    lifecycle.position[
        "stop_loss"
    ] = 106.0

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        break_even_engine=None,
        trailing_stop_engine=(
            TrailingStopEngineV2(
                activation_profit_points=5.0,
                trailing_distance_points=3.0,
            )
        ),
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=108.0,
    )

    updated = result[
        "updated_positions"
    ][0]

    assert (
        updated["position"][
            "stop_loss"
        ]
        == 106.0
    )

    assert (
        result["trailing_stop_results"][0][
            "status"
        ]
        == "ALREADY_PROTECTED"
    )


def test_monitor_without_trailing_stop_engine():
    lifecycle = (
        FakeTradeLifecycleService()
    )

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        break_even_engine=None,
        trailing_stop_engine=None,
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=108.0,
    )

    assert result["processed"] is True
    assert (
        result["trailing_stop_results"]
        == []
    )


def test_rejects_invalid_trailing_stop_engine():
    lifecycle = (
        FakeTradeLifecycleService()
    )

    with pytest.raises(
        TypeError,
        match="trailing_stop_engine",
    ):
        LivePositionMonitorV2(
            trade_lifecycle_service=lifecycle,
            break_even_engine=None,
            trailing_stop_engine=object(),
        )
