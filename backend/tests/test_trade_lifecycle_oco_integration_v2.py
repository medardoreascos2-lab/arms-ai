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
from backend.execution.oco_manager_v2 import (
    OCOManagerV2,
)
from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)
from backend.execution.position_manager_v2 import (
    PositionManagerV2,
)
from backend.execution.protective_order_registry_v2 import (
    ProtectiveOrderRegistryV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


def build_signal(
    *,
    direction: str = "LONG",
) -> dict[str, object]:
    if direction == "LONG":
        stop_loss = 22980.0
        take_profit = 23040.0
    else:
        stop_loss = 23020.0
        take_profit = 22940.0

    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": direction,
        "entry_price": 23000.0,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": f"NQ {direction}",
    }


def build_service(
    *,
    registry=None,
    oco_manager=None,
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
                slippage_points=0.0,
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
        protective_order_registry_v2=registry,
        oco_manager_v2=oco_manager,
    )


def test_creates_default_oco_manager():
    service = build_service()

    assert isinstance(
        service.oco_manager_v2,
        OCOManagerV2,
    )


def test_uses_injected_oco_manager():
    manager = OCOManagerV2()

    service = build_service(
        oco_manager=manager,
    )

    assert service.oco_manager_v2 is manager


def test_rejects_invalid_oco_manager():
    with pytest.raises(
        TypeError,
        match="oco_manager_v2",
    ):
        build_service(
            oco_manager=object(),
        )


@pytest.mark.parametrize(
    "direction",
    [
        "LONG",
        "SHORT",
    ],
)
def test_open_position_creates_oco_group(
    direction,
):
    registry = ProtectiveOrderRegistryV2()
    manager = OCOManagerV2()

    service = build_service(
        registry=registry,
        oco_manager=manager,
    )

    result = service.submit_signal(
        signal=build_signal(
            direction=direction,
        ),
        order_type="MARKET",
    )

    assert result["accepted"] is True
    assert result["position"] is not None

    position = result["position"]

    protection = registry.get_by_position(
        position_id=position["position_id"],
        active_only=True,
    )

    assert protection is not None

    group = manager.get_group_by_position(
        position_id=position["position_id"],
        active_only=True,
    )

    assert group is not None

    assert (
        group["position_id"]
        == position["position_id"]
    )

    assert (
        group["stop_order_id"]
        == protection["stop_order_id"]
    )

    assert (
        group["take_profit_order_id"]
        == protection[
            "take_profit_order_id"
        ]
    )

    assert group["status"] == "ACTIVE"

    assert (
        position["oco_group_id"]
        == group["oco_group_id"]
    )

    assert (
        position["protection_group_id"]
        == protection[
            "protection_group_id"
        ]
    )


def test_active_position_keeps_oco_group_id():
    service = build_service()

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
    )

    position = result["position"]

    assert position is not None

    stored_position = (
        service.get_active_positions()[0]
    )

    assert stored_position["oco_group_id"]

    assert (
        stored_position["oco_group_id"]
        == position["oco_group_id"]
    )


def test_oco_uses_registry_child_order_ids():
    registry = ProtectiveOrderRegistryV2()
    manager = OCOManagerV2()

    service = build_service(
        registry=registry,
        oco_manager=manager,
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
    )

    position = result["position"]

    assert position is not None

    protection = registry.get_by_position(
        position_id=position["position_id"],
        active_only=True,
    )

    group = manager.get_group(
        oco_group_id=position["oco_group_id"],
    )

    assert protection is not None
    assert group is not None

    assert (
        position["stop_order_id"]
        == protection["stop_order_id"]
        == group["stop_order_id"]
    )

    assert (
        position["take_profit_order_id"]
        == protection[
            "take_profit_order_id"
        ]
        == group["take_profit_order_id"]
    )


def test_oco_metadata_links_protection():
    registry = ProtectiveOrderRegistryV2()
    manager = OCOManagerV2()

    service = build_service(
        registry=registry,
        oco_manager=manager,
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
    )

    position = result["position"]

    assert position is not None

    group = manager.get_group(
        oco_group_id=position["oco_group_id"],
    )

    assert group is not None

    metadata = group["metadata"]

    assert (
        metadata["protection_group_id"]
        == position["protection_group_id"]
    )

    assert metadata["symbol"] == "NQ"
    assert metadata["direction"] == "LONG"

    assert (
        metadata["broker_position_id"]
        == position["broker_position_id"]
    )


def test_oco_snapshot_reports_active_group():
    service = build_service()

    service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
    )

    snapshot = service.oco_manager_v2.snapshot()

    assert snapshot["total_groups"] == 1
    assert snapshot["active_groups"] == 1
    assert snapshot["completed_groups"] == 0
    assert snapshot["cancelled_groups"] == 0


def test_registry_and_oco_have_one_active_record():
    service = build_service()

    service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
    )

    registry_snapshot = (
        service
        .protective_order_registry_v2
        .snapshot()
    )

    oco_snapshot = (
        service
        .oco_manager_v2
        .snapshot()
    )

    assert (
        registry_snapshot[
            "active_protections"
        ]
        == 1
    )

    assert oco_snapshot["active_groups"] == 1
