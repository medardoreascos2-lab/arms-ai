import pytest

from backend.execution.protective_order_registry_v2 import (
    ProtectiveOrderRegistryV2,
)


def build_registry(
) -> ProtectiveOrderRegistryV2:
    return ProtectiveOrderRegistryV2()


def create_long_protection(
    registry: ProtectiveOrderRegistryV2,
    *,
    position_id: str = "position-1",
):
    return registry.create_protection(
        position_id=position_id,
        broker_position_id="broker-position-1",
        symbol="NQ",
        direction="LONG",
        quantity=2,
        entry_price=23000.0,
        stop_price=22980.0,
        take_profit_price=23040.0,
        metadata={
            "source": "test",
        },
    )


def test_creates_long_protection():
    registry = build_registry()

    protection = create_long_protection(
        registry
    )

    assert (
        protection["position_id"]
        == "position-1"
    )
    assert (
        protection["broker_position_id"]
        == "broker-position-1"
    )
    assert protection["symbol"] == "NQ"
    assert protection["direction"] == "LONG"
    assert protection["quantity"] == 2.0
    assert protection["status"] == "ACTIVE"
    assert (
        protection["stop_order_status"]
        == "ACTIVE"
    )
    assert (
        protection[
            "take_profit_order_status"
        ]
        == "ACTIVE"
    )
    assert protection["stop_order_id"]
    assert protection["take_profit_order_id"]
    assert (
        protection["stop_order_id"]
        != protection[
            "take_profit_order_id"
        ]
    )


def test_creates_short_protection():
    registry = build_registry()

    protection = (
        registry.create_protection(
            position_id="position-short",
            symbol="NQ",
            direction="SHORT",
            quantity=1,
            entry_price=23000.0,
            stop_price=23020.0,
            take_profit_price=22960.0,
        )
    )

    assert protection["direction"] == "SHORT"
    assert protection["status"] == "ACTIVE"


@pytest.mark.parametrize(
    (
        "field_name",
        "value",
    ),
    [
        ("position_id", ""),
        ("symbol", ""),
        ("direction", ""),
    ],
)
def test_rejects_empty_required_text(
    field_name,
    value,
):
    registry = build_registry()

    arguments = {
        "position_id": "position-1",
        "symbol": "NQ",
        "direction": "LONG",
        "quantity": 2,
        "entry_price": 23000.0,
        "stop_price": 22980.0,
        "take_profit_price": 23040.0,
    }

    arguments[field_name] = value

    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        registry.create_protection(
            **arguments
        )


@pytest.mark.parametrize(
    (
        "field_name",
        "value",
    ),
    [
        ("quantity", 0),
        ("entry_price", 0),
        ("stop_price", 0),
        ("take_profit_price", 0),
    ],
)
def test_rejects_non_positive_numbers(
    field_name,
    value,
):
    registry = build_registry()

    arguments = {
        "position_id": "position-1",
        "symbol": "NQ",
        "direction": "LONG",
        "quantity": 2,
        "entry_price": 23000.0,
        "stop_price": 22980.0,
        "take_profit_price": 23040.0,
    }

    arguments[field_name] = value

    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        registry.create_protection(
            **arguments
        )


def test_rejects_invalid_direction():
    registry = build_registry()

    with pytest.raises(
        ValueError,
        match="direction",
    ):
        registry.create_protection(
            position_id="position-1",
            symbol="NQ",
            direction="SIDEWAYS",
            quantity=2,
            entry_price=23000.0,
            stop_price=22980.0,
            take_profit_price=23040.0,
        )


@pytest.mark.parametrize(
    (
        "stop_price",
        "take_profit_price",
    ),
    [
        (23000.0, 23040.0),
        (23020.0, 23040.0),
        (22980.0, 23000.0),
        (22980.0, 22960.0),
    ],
)
def test_validates_long_price_structure(
    stop_price,
    take_profit_price,
):
    registry = build_registry()

    with pytest.raises(ValueError):
        registry.create_protection(
            position_id="position-1",
            symbol="NQ",
            direction="LONG",
            quantity=2,
            entry_price=23000.0,
            stop_price=stop_price,
            take_profit_price=(
                take_profit_price
            ),
        )


@pytest.mark.parametrize(
    (
        "stop_price",
        "take_profit_price",
    ),
    [
        (23000.0, 22960.0),
        (22980.0, 22960.0),
        (23020.0, 23000.0),
        (23020.0, 23040.0),
    ],
)
def test_validates_short_price_structure(
    stop_price,
    take_profit_price,
):
    registry = build_registry()

    with pytest.raises(ValueError):
        registry.create_protection(
            position_id="position-1",
            symbol="NQ",
            direction="SHORT",
            quantity=2,
            entry_price=23000.0,
            stop_price=stop_price,
            take_profit_price=(
                take_profit_price
            ),
        )


def test_prevents_two_active_protections():
    registry = build_registry()

    create_long_protection(
        registry,
        position_id="same-position",
    )

    with pytest.raises(
        ValueError,
        match="protección activa",
    ):
        create_long_protection(
            registry,
            position_id="same-position",
        )


def test_supports_explicit_identifiers():
    registry = build_registry()

    protection = (
        registry.create_protection(
            protection_group_id="group-1",
            position_id="position-1",
            symbol="NQ",
            direction="LONG",
            quantity=2,
            entry_price=23000.0,
            stop_price=22980.0,
            take_profit_price=23040.0,
            stop_order_id="stop-1",
            take_profit_order_id="tp-1",
        )
    )

    assert (
        protection["protection_group_id"]
        == "group-1"
    )
    assert (
        protection["stop_order_id"]
        == "stop-1"
    )
    assert (
        protection["take_profit_order_id"]
        == "tp-1"
    )


def test_rejects_equal_order_ids():
    registry = build_registry()

    with pytest.raises(
        ValueError,
        match="diferentes",
    ):
        registry.create_protection(
            position_id="position-1",
            symbol="NQ",
            direction="LONG",
            quantity=2,
            entry_price=23000.0,
            stop_price=22980.0,
            take_profit_price=23040.0,
            stop_order_id="order-1",
            take_profit_order_id="order-1",
        )


def test_gets_protection_by_group():
    registry = build_registry()

    created = create_long_protection(
        registry
    )

    found = registry.get_protection(
        protection_group_id=created[
            "protection_group_id"
        ]
    )

    assert found == created


def test_gets_protection_by_position():
    registry = build_registry()

    created = create_long_protection(
        registry
    )

    found = registry.get_by_position(
        position_id="position-1",
        active_only=True,
    )

    assert found == created


def test_returns_defensive_copies():
    registry = build_registry()

    created = create_long_protection(
        registry
    )

    created["status"] = "CORRUPTED"
    created["metadata"]["source"] = (
        "corrupted"
    )

    stored = registry.get_by_position(
        position_id="position-1",
    )

    assert stored["status"] == "ACTIVE"
    assert (
        stored["metadata"]["source"]
        == "test"
    )


def test_lists_and_filters_protections():
    registry = build_registry()

    first = create_long_protection(
        registry,
        position_id="position-1",
    )

    create_long_protection(
        registry,
        position_id="position-2",
    )

    registry.cancel_protection(
        protection_group_id=first[
            "protection_group_id"
        ]
    )

    assert len(
        registry.list_protections()
    ) == 2

    assert len(
        registry.list_protections(
            status="ACTIVE"
        )
    ) == 1

    assert len(
        registry.list_protections(
            status="CANCELLED"
        )
    ) == 1


def test_completes_stop_protection():
    registry = build_registry()

    created = create_long_protection(
        registry
    )

    completed = (
        registry.complete_protection(
            protection_group_id=created[
                "protection_group_id"
            ],
            triggered_order_id=created[
                "stop_order_id"
            ],
            reason="STOP_LOSS",
        )
    )

    assert completed["status"] == "COMPLETED"
    assert (
        completed["stop_order_status"]
        == "FILLED"
    )
    assert (
        completed[
            "take_profit_order_status"
        ]
        == "CANCELLED"
    )
    assert (
        completed["triggered_order_id"]
        == created["stop_order_id"]
    )
    assert (
        completed["cancelled_order_id"]
        == created[
            "take_profit_order_id"
        ]
    )


def test_completes_take_profit_protection():
    registry = build_registry()

    created = create_long_protection(
        registry
    )

    completed = (
        registry.complete_protection(
            protection_group_id=created[
                "protection_group_id"
            ],
            triggered_order_id=created[
                "take_profit_order_id"
            ],
            reason="TAKE_PROFIT",
        )
    )

    assert completed["status"] == "COMPLETED"
    assert (
        completed[
            "take_profit_order_status"
        ]
        == "FILLED"
    )
    assert (
        completed["stop_order_status"]
        == "CANCELLED"
    )


def test_completion_is_idempotent():
    registry = build_registry()

    created = create_long_protection(
        registry
    )

    first = registry.complete_protection(
        protection_group_id=created[
            "protection_group_id"
        ],
        triggered_order_id=created[
            "stop_order_id"
        ],
        reason="STOP_LOSS",
    )

    second = registry.complete_protection(
        protection_group_id=created[
            "protection_group_id"
        ],
        triggered_order_id=created[
            "stop_order_id"
        ],
        reason="STOP_LOSS",
    )

    assert second == first


def test_rejects_foreign_trigger_order():
    registry = build_registry()

    created = create_long_protection(
        registry
    )

    with pytest.raises(
        ValueError,
        match="no pertenece",
    ):
        registry.complete_protection(
            protection_group_id=created[
                "protection_group_id"
            ],
            triggered_order_id=(
                "foreign-order"
            ),
            reason="TEST",
        )


def test_cancels_protection():
    registry = build_registry()

    created = create_long_protection(
        registry
    )

    cancelled = (
        registry.cancel_protection(
            protection_group_id=created[
                "protection_group_id"
            ],
            reason="POSITION_CLOSED",
        )
    )

    assert cancelled["status"] == "CANCELLED"
    assert (
        cancelled["stop_order_status"]
        == "CANCELLED"
    )
    assert (
        cancelled[
            "take_profit_order_status"
        ]
        == "CANCELLED"
    )
    assert (
        cancelled["completion_reason"]
        == "POSITION_CLOSED"
    )


def test_cancellation_is_idempotent():
    registry = build_registry()

    created = create_long_protection(
        registry
    )

    first = registry.cancel_protection(
        protection_group_id=created[
            "protection_group_id"
        ]
    )

    second = registry.cancel_protection(
        protection_group_id=created[
            "protection_group_id"
        ]
    )

    assert second == first


def test_cannot_remove_active_protection():
    registry = build_registry()

    created = create_long_protection(
        registry
    )

    with pytest.raises(
        ValueError,
        match="activa",
    ):
        registry.remove_protection(
            protection_group_id=created[
                "protection_group_id"
            ]
        )


def test_removes_cancelled_protection():
    registry = build_registry()

    created = create_long_protection(
        registry
    )

    registry.cancel_protection(
        protection_group_id=created[
            "protection_group_id"
        ]
    )

    removed = registry.remove_protection(
        protection_group_id=created[
            "protection_group_id"
        ]
    )

    assert removed is True

    assert (
        registry.get_protection(
            protection_group_id=created[
                "protection_group_id"
            ]
        )
        is None
    )


def test_snapshot():
    registry = build_registry()

    active = create_long_protection(
        registry,
        position_id="position-active",
    )

    cancelled = create_long_protection(
        registry,
        position_id="position-cancelled",
    )

    completed = create_long_protection(
        registry,
        position_id="position-completed",
    )

    registry.cancel_protection(
        protection_group_id=cancelled[
            "protection_group_id"
        ]
    )

    registry.complete_protection(
        protection_group_id=completed[
            "protection_group_id"
        ],
        triggered_order_id=completed[
            "take_profit_order_id"
        ],
        reason="TAKE_PROFIT",
    )

    snapshot = registry.snapshot()

    assert snapshot["status"] == "READY"
    assert snapshot["total_protections"] == 3
    assert snapshot["active_protections"] == 1
    assert (
        snapshot["cancelled_protections"]
        == 1
    )
    assert (
        snapshot["completed_protections"]
        == 1
    )
    assert len(snapshot["protections"]) == 3

    assert active["status"] == "ACTIVE"


def test_rejects_invalid_status_filter():
    registry = build_registry()

    with pytest.raises(
        ValueError,
        match="status",
    ):
        registry.list_protections(
            status="UNKNOWN"
        )
