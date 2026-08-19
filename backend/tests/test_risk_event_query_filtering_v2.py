from __future__ import annotations

from backend.risk.risk_event_store_v2 import (
    RiskEventStoreV2,
)


def build_event(
    *,
    timestamp: str,
    event_type: str,
    symbol: str,
    reason: str,
) -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "event_type": event_type,
        "symbol": symbol,
        "reason": reason,
    }


def build_store(tmp_path):
    store = RiskEventStoreV2(
        path=tmp_path / "risk-events.json",
    )

    store.append(
        build_event(
            timestamp="2026-08-19T10:00:00+00:00",
            event_type="RISK_APPROVED",
            symbol="NQ",
            reason="APPROVED",
        )
    )

    store.append(
        build_event(
            timestamp="2026-08-19T11:00:00+00:00",
            event_type="RISK_BLOCKED",
            symbol="MNQ",
            reason="DAILY_LIMIT",
        )
    )

    store.append(
        build_event(
            timestamp="2026-08-19T12:00:00+00:00",
            event_type="RISK_BLOCKED",
            symbol="NQ",
            reason="EXPOSURE_LIMIT",
        )
    )

    store.append(
        build_event(
            timestamp="2026-08-19T13:00:00+00:00",
            event_type="RISK_APPROVED",
            symbol="ES",
            reason="APPROVED",
        )
    )

    return store


def test_query_without_filters_returns_all_events(
    tmp_path,
):
    store = build_store(tmp_path)

    result = store.query_events()

    assert len(result) == 4


def test_query_filters_by_symbol(
    tmp_path,
):
    store = build_store(tmp_path)

    result = store.query_events(
        symbol="NQ",
    )

    assert len(result) == 2

    assert all(
        event["symbol"] == "NQ"
        for event in result
    )


def test_query_symbol_is_case_insensitive(
    tmp_path,
):
    store = build_store(tmp_path)

    result = store.query_events(
        symbol="nq",
    )

    assert len(result) == 2


def test_query_filters_by_event_type(
    tmp_path,
):
    store = build_store(tmp_path)

    result = store.query_events(
        event_type="RISK_BLOCKED",
    )

    assert len(result) == 2

    assert all(
        event["event_type"] == "RISK_BLOCKED"
        for event in result
    )


def test_query_combines_filters(
    tmp_path,
):
    store = build_store(tmp_path)

    result = store.query_events(
        symbol="NQ",
        event_type="RISK_BLOCKED",
    )

    assert len(result) == 1
    assert result[0]["reason"] == "EXPOSURE_LIMIT"


def test_query_supports_limit(
    tmp_path,
):
    store = build_store(tmp_path)

    result = store.query_events(
        limit=2,
    )

    assert len(result) == 2


def test_query_limit_returns_latest_events(
    tmp_path,
):
    store = build_store(tmp_path)

    result = store.query_events(
        limit=2,
    )

    assert [
        event["timestamp"]
        for event in result
    ] == [
        "2026-08-19T12:00:00+00:00",
        "2026-08-19T13:00:00+00:00",
    ]


def test_query_supports_offset(
    tmp_path,
):
    store = build_store(tmp_path)

    result = store.query_events(
        offset=1,
        limit=2,
    )

    assert [
        event["timestamp"]
        for event in result
    ] == [
        "2026-08-19T11:00:00+00:00",
        "2026-08-19T12:00:00+00:00",
    ]


def test_query_supports_start_timestamp(
    tmp_path,
):
    store = build_store(tmp_path)

    result = store.query_events(
        start_timestamp=(
            "2026-08-19T12:00:00+00:00"
        ),
    )

    assert len(result) == 2


def test_query_supports_end_timestamp(
    tmp_path,
):
    store = build_store(tmp_path)

    result = store.query_events(
        end_timestamp=(
            "2026-08-19T11:00:00+00:00"
        ),
    )

    assert len(result) == 2


def test_query_supports_timestamp_range(
    tmp_path,
):
    store = build_store(tmp_path)

    result = store.query_events(
        start_timestamp=(
            "2026-08-19T11:00:00+00:00"
        ),
        end_timestamp=(
            "2026-08-19T12:00:00+00:00"
        ),
    )

    assert len(result) == 2


def test_query_returns_copy(
    tmp_path,
):
    store = build_store(tmp_path)

    result = store.query_events(
        symbol="NQ",
    )

    result[0]["reason"] = "MUTATED"

    fresh = store.query_events(
        symbol="NQ",
    )

    assert fresh[0]["reason"] != "MUTATED"


def test_query_rejects_invalid_limit(
    tmp_path,
):
    store = build_store(tmp_path)

    try:
        store.query_events(
            limit=0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError"
        )


def test_query_rejects_negative_offset(
    tmp_path,
):
    store = build_store(tmp_path)

    try:
        store.query_events(
            offset=-1,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError"
        )
