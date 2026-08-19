import json

import pytest

from backend.risk.risk_event_store_v2 import (
    RiskEventStoreV2,
)


def _event(
    *,
    symbol: str = "NQ",
    reason: str = "TEST",
    risk: float = 50.0,
):
    return {
        "timestamp": "2026-08-19T16:50:03+00:00",
        "symbol": symbol,
        "side": "SELL",
        "contracts": 1,
        "risk": risk,
        "status": "BLOCKED",
        "reason": reason,
    }


def test_store_persists_event_to_disk(
    tmp_path,
):
    path = tmp_path / "risk_events.json"

    store = RiskEventStoreV2(
        path=path,
    )

    event = _event()

    store.append(event)

    assert path.exists()

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    assert payload == [event]


def test_new_store_instance_restores_events(
    tmp_path,
):
    path = tmp_path / "risk_events.json"

    store1 = RiskEventStoreV2(
        path=path,
    )

    event = _event(
        reason="RESTART_TEST",
    )

    store1.append(event)

    store2 = RiskEventStoreV2(
        path=path,
    )

    assert store2.get_events() == [
        event
    ]


def test_get_events_returns_copy(
    tmp_path,
):
    path = tmp_path / "risk_events.json"

    store = RiskEventStoreV2(
        path=path,
    )

    store.append(
        _event()
    )

    events = store.get_events()

    events.clear()

    assert len(
        store.get_events()
    ) == 1


def test_append_does_not_expose_input_reference(
    tmp_path,
):
    path = tmp_path / "risk_events.json"

    store = RiskEventStoreV2(
        path=path,
    )

    event = _event()

    store.append(event)

    event["reason"] = "MUTATED"

    assert (
        store.get_events()[0]["reason"]
        == "TEST"
    )


def test_store_enforces_max_events(
    tmp_path,
):
    path = tmp_path / "risk_events.json"

    store = RiskEventStoreV2(
        path=path,
        max_events=2,
    )

    store.append(
        _event(
            symbol="NQ",
            reason="ONE",
        )
    )

    store.append(
        _event(
            symbol="MNQ",
            reason="TWO",
        )
    )

    store.append(
        _event(
            symbol="ES",
            reason="THREE",
        )
    )

    events = store.get_events()

    assert len(events) == 2

    assert [
        event["reason"]
        for event in events
    ] == [
        "TWO",
        "THREE",
    ]

    store2 = RiskEventStoreV2(
        path=path,
        max_events=2,
    )

    assert [
        event["reason"]
        for event in store2.get_events()
    ] == [
        "TWO",
        "THREE",
    ]


def test_invalid_max_events_rejected(
    tmp_path,
):
    with pytest.raises(
        ValueError
    ):
        RiskEventStoreV2(
            path=(
                tmp_path
                / "risk_events.json"
            ),
            max_events=0,
        )


def test_append_requires_dict(
    tmp_path,
):
    store = RiskEventStoreV2(
        path=(
            tmp_path
            / "risk_events.json"
        ),
    )

    with pytest.raises(
        TypeError
    ):
        store.append(
            "invalid"
        )


def test_missing_file_starts_empty(
    tmp_path,
):
    store = RiskEventStoreV2(
        path=(
            tmp_path
            / "risk_events.json"
        ),
    )

    assert store.get_events() == []


def test_corrupt_json_is_rejected(
    tmp_path,
):
    path = tmp_path / "risk_events.json"

    path.write_text(
        "{broken-json",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError
    ):
        RiskEventStoreV2(
            path=path,
        )


def test_non_list_json_is_rejected(
    tmp_path,
):
    path = tmp_path / "risk_events.json"

    path.write_text(
        json.dumps(
            {
                "unexpected": True,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError
    ):
        RiskEventStoreV2(
            path=path,
        )


def test_parent_directory_created(
    tmp_path,
):
    path = (
        tmp_path
        / "nested"
        / "risk"
        / "risk_events.json"
    )

    store = RiskEventStoreV2(
        path=path,
    )

    store.append(
        _event()
    )

    assert path.exists()


def test_clear_removes_persisted_events(
    tmp_path,
):
    path = tmp_path / "risk_events.json"

    store = RiskEventStoreV2(
        path=path,
    )

    store.append(
        _event()
    )

    store.clear()

    assert store.get_events() == []

    store2 = RiskEventStoreV2(
        path=path,
    )

    assert store2.get_events() == []
