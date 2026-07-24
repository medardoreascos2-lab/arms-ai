import pytest

from backend.execution.break_even_engine_v2 import (
    BreakEvenEngineV2,
)
from backend.execution.partial_take_profit_engine_v2 import (
    PartialTakeProfitEngineV2,
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
            "quantity": 2.0,
            "entry_price": 100.0,
            "current_price": 100.0,
            "stop_loss": 95.0,
            "take_profit": 120.0,
            "partial_taken": False,
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


def test_partial_take_profit_is_applied_before_break_even_and_trailing():
    lifecycle = (
        FakeTradeLifecycleService()
    )

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        partial_take_profit_engine=(
            PartialTakeProfitEngineV2(
                trigger_profit_points=10.0,
                close_fraction=0.50,
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

    result = monitor.process_price(
        symbol="NQ",
        current_price=110.0,
    )

    updated = result[
        "updated_positions"
    ][0]

    position = updated[
        "position"
    ]

    assert position[
        "partial_taken"
    ] is True

    assert position[
        "quantity"
    ] == 1.0

    assert position[
        "partial_closed_quantity"
    ] == 1.0

    assert position[
        "stop_loss"
    ] == 107.0

    assert len(
        result[
            "partial_take_profit_results"
        ]
    ) == 1

    assert (
        result[
            "partial_take_profit_results"
        ][0][
            "status"
        ]
        == "PARTIAL_TAKEN"
    )


def test_partial_take_profit_waits_before_trigger():
    lifecycle = (
        FakeTradeLifecycleService()
    )

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        partial_take_profit_engine=(
            PartialTakeProfitEngineV2(
                trigger_profit_points=10.0,
                close_fraction=0.50,
            )
        ),
        break_even_engine=None,
        trailing_stop_engine=None,
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=108.0,
    )

    position = result[
        "updated_positions"
    ][0][
        "position"
    ]

    assert position[
        "quantity"
    ] == 2.0

    assert position[
        "partial_taken"
    ] is False

    assert (
        result[
            "partial_take_profit_results"
        ][0][
            "status"
        ]
        == "WAITING"
    )


def test_partial_take_profit_is_not_executed_twice():
    lifecycle = (
        FakeTradeLifecycleService()
    )

    lifecycle.position[
        "partial_taken"
    ] = True

    lifecycle.position[
        "quantity"
    ] = 1.0

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        partial_take_profit_engine=(
            PartialTakeProfitEngineV2(
                trigger_profit_points=10.0,
                close_fraction=0.50,
            )
        ),
        break_even_engine=None,
        trailing_stop_engine=None,
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=110.0,
    )

    position = result[
        "updated_positions"
    ][0][
        "position"
    ]

    assert position[
        "quantity"
    ] == 1.0

    assert (
        result[
            "partial_take_profit_results"
        ][0][
            "status"
        ]
        == "ALREADY_EXECUTED"
    )


def test_monitor_without_partial_take_profit_engine():
    lifecycle = (
        FakeTradeLifecycleService()
    )

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        partial_take_profit_engine=None,
        break_even_engine=None,
        trailing_stop_engine=None,
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=110.0,
    )

    assert result["processed"] is True

    assert (
        result[
            "partial_take_profit_results"
        ]
        == []
    )


def test_rejects_invalid_partial_take_profit_engine():
    lifecycle = (
        FakeTradeLifecycleService()
    )

    with pytest.raises(
        TypeError,
        match=(
            "partial_take_profit_engine"
        ),
    ):
        LivePositionMonitorV2(
            trade_lifecycle_service=lifecycle,
            partial_take_profit_engine=(
                object()
            ),
            break_even_engine=None,
            trailing_stop_engine=None,
        )
