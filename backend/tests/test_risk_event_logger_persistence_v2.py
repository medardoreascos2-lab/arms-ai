from __future__ import annotations

from backend.risk.risk_event_logger_v1 import (
    RiskEventLoggerV1,
)
from backend.risk.risk_event_store_v2 import (
    RiskEventStoreV2,
)


def _event(
    *,
    status: str = "APPROVED",
) -> dict:
    return {
        "symbol": "NQ",
        "side": "BUY",
        "contracts": 1,
        "risk": 50.0,
        "status": status,
    }


def test_logger_can_use_persistent_store(
    tmp_path,
):
    path = tmp_path / "risk_events.json"

    store = RiskEventStoreV2(
        path=path,
    )

    logger = RiskEventLoggerV1(
        store=store,
    )

    record = logger.log_event(
        _event(),
    )

    persisted = store.get_events()

    assert len(persisted) == 1
    assert persisted[0] == record


def test_logger_restores_events_after_restart(
    tmp_path,
):
    path = tmp_path / "risk_events.json"

    store1 = RiskEventStoreV2(
        path=path,
    )

    logger1 = RiskEventLoggerV1(
        store=store1,
    )

    first = logger1.log_event(
        _event(
            status="BLOCKED",
        ),
    )

    store2 = RiskEventStoreV2(
        path=path,
    )

    logger2 = RiskEventLoggerV1(
        store=store2,
    )

    events = logger2.get_events()

    assert len(events) == 1
    assert events[0] == first
    assert events[0]["status"] == "BLOCKED"


def test_logger_get_events_returns_copy_with_store(
    tmp_path,
):
    path = tmp_path / "risk_events.json"

    store = RiskEventStoreV2(
        path=path,
    )

    logger = RiskEventLoggerV1(
        store=store,
    )

    logger.log_event(
        _event(),
    )

    events = logger.get_events()

    events.append(
        {
            "status": "MUTATED",
        }
    )

    persisted = logger.get_events()

    assert len(persisted) == 1
    assert persisted[0]["status"] == "APPROVED"


def test_logger_preserves_legacy_in_memory_mode():
    logger = RiskEventLoggerV1()

    record = logger.log_event(
        _event(),
    )

    events = logger.get_events()

    assert len(events) == 1
    assert events[0] == record


def test_logger_persistent_record_has_timestamp(
    tmp_path,
):
    path = tmp_path / "risk_events.json"

    logger = RiskEventLoggerV1(
        store=RiskEventStoreV2(
            path=path,
        ),
    )

    record = logger.log_event(
        _event(),
    )

    assert isinstance(
        record["timestamp"],
        str,
    )

    assert record["timestamp"]


def test_store_receives_independent_record_copy(
    tmp_path,
):
    path = tmp_path / "risk_events.json"

    store = RiskEventStoreV2(
        path=path,
    )

    logger = RiskEventLoggerV1(
        store=store,
    )

    event = _event()

    record = logger.log_event(
        event,
    )

    event["status"] = "MUTATED"
    record["status"] = "MUTATED"

    persisted = store.get_events()

    assert len(persisted) == 1
    assert persisted[0]["status"] == "APPROVED"
