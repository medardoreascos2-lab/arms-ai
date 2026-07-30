import pytest

from backend.execution.oco_manager_v2 import (
    OCOManagerV2,
)


def build_manager() -> OCOManagerV2:
    return OCOManagerV2()


def create_group(
    manager: OCOManagerV2,
    *,
    position_id: str = "position-1",
    stop_order_id: str = "stop-1",
    take_profit_order_id: str = "tp-1",
) -> dict[str, object]:
    return manager.create_group(
        oco_group_id="oco-1",
        position_id=position_id,
        stop_order_id=stop_order_id,
        take_profit_order_id=(
            take_profit_order_id
        ),
        metadata={
            "symbol": "NQ",
        },
    )


def test_creates_active_group():
    manager = build_manager()

    group = create_group(manager)

    assert group["oco_group_id"] == "oco-1"
    assert group["position_id"] == "position-1"
    assert group["stop_order_id"] == "stop-1"
    assert (
        group["take_profit_order_id"]
        == "tp-1"
    )
    assert group["status"] == "ACTIVE"
    assert (
        group["stop_order_status"]
        == "ACTIVE"
    )
    assert (
        group[
            "take_profit_order_status"
        ]
        == "ACTIVE"
    )
    assert group["metadata"] == {
        "symbol": "NQ",
    }


def test_generates_group_id_when_missing():
    manager = build_manager()

    group = manager.create_group(
        position_id="position-1",
        stop_order_id="stop-1",
        take_profit_order_id="tp-1",
    )

    assert group["oco_group_id"]
    assert group["status"] == "ACTIVE"


@pytest.mark.parametrize(
    (
        "field_name",
        "kwargs",
    ),
    [
        (
            "position_id",
            {
                "position_id": "",
                "stop_order_id": "stop-1",
                "take_profit_order_id": "tp-1",
            },
        ),
        (
            "stop_order_id",
            {
                "position_id": "position-1",
                "stop_order_id": "",
                "take_profit_order_id": "tp-1",
            },
        ),
        (
            "take_profit_order_id",
            {
                "position_id": "position-1",
                "stop_order_id": "stop-1",
                "take_profit_order_id": "",
            },
        ),
    ],
)
def test_rejects_missing_required_ids(
    field_name,
    kwargs,
):
    manager = build_manager()

    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        manager.create_group(**kwargs)


def test_rejects_equal_order_ids():
    manager = build_manager()

    with pytest.raises(
        ValueError,
        match="deben ser diferentes",
    ):
        manager.create_group(
            position_id="position-1",
            stop_order_id="order-1",
            take_profit_order_id="order-1",
        )


def test_rejects_duplicate_group_id():
    manager = build_manager()
    create_group(manager)

    with pytest.raises(
        ValueError,
        match="Ya existe",
    ):
        create_group(
            manager,
            position_id="position-2",
            stop_order_id="stop-2",
            take_profit_order_id="tp-2",
        )


def test_rejects_second_active_group_for_position():
    manager = build_manager()
    create_group(manager)

    with pytest.raises(
        ValueError,
        match="activo para esta posición",
    ):
        manager.create_group(
            oco_group_id="oco-2",
            position_id="position-1",
            stop_order_id="stop-2",
            take_profit_order_id="tp-2",
        )


def test_gets_group_by_id():
    manager = build_manager()
    create_group(manager)

    group = manager.get_group(
        oco_group_id="oco-1",
    )

    assert group is not None
    assert group["position_id"] == "position-1"


def test_returns_none_for_missing_group():
    manager = build_manager()

    assert (
        manager.get_group(
            oco_group_id="missing",
        )
        is None
    )


def test_gets_group_by_position():
    manager = build_manager()
    create_group(manager)

    group = manager.get_group_by_position(
        position_id="position-1",
        active_only=True,
    )

    assert group is not None
    assert group["oco_group_id"] == "oco-1"


def test_stop_fill_cancels_take_profit():
    manager = build_manager()
    create_group(manager)

    result = manager.cancel_remaining(
        oco_group_id="oco-1",
        triggered_order_id="stop-1",
        reason="STOP_LOSS_FILLED",
    )

    assert result["completed"] is True
    assert result["status"] == "COMPLETED"
    assert (
        result["triggered_order_id"]
        == "stop-1"
    )
    assert (
        result["cancelled_order_id"]
        == "tp-1"
    )

    group = result["group"]

    assert group["status"] == "COMPLETED"
    assert (
        group["stop_order_status"]
        == "FILLED"
    )
    assert (
        group[
            "take_profit_order_status"
        ]
        == "CANCELLED"
    )
    assert (
        group["completion_reason"]
        == "STOP_LOSS_FILLED"
    )
    assert group["completed_at"]


def test_take_profit_fill_cancels_stop():
    manager = build_manager()
    create_group(manager)

    result = manager.cancel_remaining(
        oco_group_id="oco-1",
        triggered_order_id="tp-1",
        reason="TAKE_PROFIT_FILLED",
    )

    assert result["completed"] is True
    assert (
        result["cancelled_order_id"]
        == "stop-1"
    )

    group = result["group"]

    assert (
        group[
            "take_profit_order_status"
        ]
        == "FILLED"
    )
    assert (
        group["stop_order_status"]
        == "CANCELLED"
    )


def test_resolution_is_idempotent():
    manager = build_manager()
    create_group(manager)

    first = manager.cancel_remaining(
        oco_group_id="oco-1",
        triggered_order_id="tp-1",
    )

    second = manager.cancel_remaining(
        oco_group_id="oco-1",
        triggered_order_id="tp-1",
    )

    assert first["completed"] is True
    assert second["completed"] is True
    assert second["idempotent"] is True
    assert (
        second["status"]
        == "ALREADY_COMPLETED"
    )
    assert (
        second["cancelled_order_id"]
        == "stop-1"
    )


def test_rejects_different_trigger_after_resolution():
    manager = build_manager()
    create_group(manager)

    manager.cancel_remaining(
        oco_group_id="oco-1",
        triggered_order_id="tp-1",
    )

    result = manager.cancel_remaining(
        oco_group_id="oco-1",
        triggered_order_id="stop-1",
    )

    assert result["completed"] is False
    assert (
        result["status"]
        == "GROUP_ALREADY_RESOLVED"
    )


def test_rejects_order_not_in_group():
    manager = build_manager()
    create_group(manager)

    result = manager.cancel_remaining(
        oco_group_id="oco-1",
        triggered_order_id="unknown-order",
    )

    assert result["completed"] is False
    assert (
        result["status"]
        == "ORDER_NOT_IN_GROUP"
    )

    stored = manager.get_group(
        oco_group_id="oco-1",
    )

    assert stored is not None
    assert stored["status"] == "ACTIVE"


def test_returns_not_found_when_resolving():
    manager = build_manager()

    result = manager.cancel_remaining(
        oco_group_id="missing",
        triggered_order_id="stop-1",
    )

    assert result["completed"] is False
    assert result["status"] == "NOT_FOUND"


def test_cancels_entire_group_manually():
    manager = build_manager()
    create_group(manager)

    result = manager.cancel_group(
        oco_group_id="oco-1",
        reason="POSITION_CLOSED_MANUALLY",
    )

    assert result["cancelled"] is True
    assert result["status"] == "CANCELLED"

    group = result["group"]

    assert group["status"] == "CANCELLED"
    assert (
        group["stop_order_status"]
        == "CANCELLED"
    )
    assert (
        group[
            "take_profit_order_status"
        ]
        == "CANCELLED"
    )
    assert (
        group["completion_reason"]
        == "POSITION_CLOSED_MANUALLY"
    )


def test_manual_cancel_is_idempotent():
    manager = build_manager()
    create_group(manager)

    manager.cancel_group(
        oco_group_id="oco-1",
    )

    result = manager.cancel_group(
        oco_group_id="oco-1",
    )

    assert result["cancelled"] is True
    assert result["idempotent"] is True
    assert (
        result["status"]
        == "ALREADY_CANCELLED"
    )


def test_cannot_cancel_completed_group():
    manager = build_manager()
    create_group(manager)

    manager.cancel_remaining(
        oco_group_id="oco-1",
        triggered_order_id="tp-1",
    )

    result = manager.cancel_group(
        oco_group_id="oco-1",
    )

    assert result["cancelled"] is False
    assert (
        result["status"]
        == "GROUP_ALREADY_COMPLETED"
    )


def test_cannot_remove_active_group():
    manager = build_manager()
    create_group(manager)

    result = manager.remove_group(
        oco_group_id="oco-1",
    )

    assert result["removed"] is False
    assert (
        result["status"]
        == "ACTIVE_GROUP_CANNOT_BE_REMOVED"
    )


def test_removes_completed_group():
    manager = build_manager()
    create_group(manager)

    manager.cancel_remaining(
        oco_group_id="oco-1",
        triggered_order_id="tp-1",
    )

    result = manager.remove_group(
        oco_group_id="oco-1",
    )

    assert result["removed"] is True
    assert result["status"] == "REMOVED"
    assert (
        manager.get_group(
            oco_group_id="oco-1",
        )
        is None
    )


def test_lists_groups_by_status():
    manager = build_manager()

    manager.create_group(
        oco_group_id="oco-active",
        position_id="position-active",
        stop_order_id="stop-active",
        take_profit_order_id="tp-active",
    )

    manager.create_group(
        oco_group_id="oco-completed",
        position_id="position-completed",
        stop_order_id="stop-completed",
        take_profit_order_id="tp-completed",
    )

    manager.cancel_remaining(
        oco_group_id="oco-completed",
        triggered_order_id="tp-completed",
    )

    active = manager.list_groups(
        status="ACTIVE",
    )

    completed = manager.list_groups(
        status="COMPLETED",
    )

    assert len(active) == 1
    assert (
        active[0]["oco_group_id"]
        == "oco-active"
    )

    assert len(completed) == 1
    assert (
        completed[0]["oco_group_id"]
        == "oco-completed"
    )


def test_snapshot_reports_group_totals():
    manager = build_manager()

    manager.create_group(
        oco_group_id="oco-active",
        position_id="position-active",
        stop_order_id="stop-active",
        take_profit_order_id="tp-active",
    )

    manager.create_group(
        oco_group_id="oco-completed",
        position_id="position-completed",
        stop_order_id="stop-completed",
        take_profit_order_id="tp-completed",
    )

    manager.create_group(
        oco_group_id="oco-cancelled",
        position_id="position-cancelled",
        stop_order_id="stop-cancelled",
        take_profit_order_id="tp-cancelled",
    )

    manager.cancel_remaining(
        oco_group_id="oco-completed",
        triggered_order_id="tp-completed",
    )

    manager.cancel_group(
        oco_group_id="oco-cancelled",
    )

    snapshot = manager.snapshot()

    assert snapshot["total_groups"] == 3
    assert snapshot["active_groups"] == 1
    assert snapshot["completed_groups"] == 1
    assert snapshot["cancelled_groups"] == 1


def test_returned_group_is_a_copy():
    manager = build_manager()
    created = create_group(manager)

    created["status"] = "CORRUPTED"

    stored = manager.get_group(
        oco_group_id="oco-1",
    )

    assert stored is not None
    assert stored["status"] == "ACTIVE"
