import json
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest


MODULE = (
    "backend.services."
    "sim_native_runtime_snapshot_reader_v2"
)


def load_reader():
    module = __import__(
        MODULE,
        fromlist=[
            "SimNativeRuntimeSnapshotReaderV2"
        ],
    )

    return (
        module
        .SimNativeRuntimeSnapshotReaderV2
    )


NOW = datetime(
    2026,
    9,
    27,
    2,
    30,
    0,
    tzinfo=timezone.utc,
)


def payload(
    *,
    observed_at=None,
    account_name="Sim101",
    provider="Simulator",
    connection_status="Connected",
    instrument="NQ DEC26",
    physical_test_readiness="PHYSICAL_TEST_READY",
    position_state="FLAT",
    active_order_count=0,
    native_submit_enabled=False,
    auto_retry_allowed=False,
):
    if observed_at is None:
        observed_at = (
            NOW - timedelta(seconds=1)
        ).isoformat()

    return {
        "schema":
            "arms.nt.sim-runtime-readiness.v2",
        "observed_at": observed_at,
        "account_name": account_name,
        "provider": provider,
        "connection_status":
            connection_status,
        "instrument": instrument,
        "physical_test_readiness":
            physical_test_readiness,
        "position_state": position_state,
        "active_order_count":
            active_order_count,
        "native_submit_enabled":
            native_submit_enabled,
        "auto_retry_allowed":
            auto_retry_allowed,
    }


def write_snapshot(
    directory,
    value,
):
    path = (
        directory
        / "sim-native-runtime-snapshot-v2.json"
    )

    path.write_text(
        json.dumps(
            value,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    return path


def build(tmp_path):
    Reader = load_reader()

    return Reader(
        snapshot_directory=tmp_path,
        instrument="NQ DEC26",
        clock=lambda: NOW,
        maximum_age_seconds=15,
    )


def test_valid_snapshot_returns_runtime_projection(
    tmp_path,
):
    write_snapshot(
        tmp_path,
        payload(),
    )

    reader = build(tmp_path)

    result = reader.snapshot()

    assert result == {
        "account_name": "Sim101",
        "provider": "Simulator",
        "connection_status": "Connected",
        "physical_test_readiness":
            "PHYSICAL_TEST_READY",
        "position_state": "FLAT",
        "active_order_count": 0,
        "native_submit_enabled": False,
        "auto_retry_allowed": False,
    }


def test_missing_snapshot_fails_closed(
    tmp_path,
):
    reader = build(tmp_path)

    with pytest.raises(RuntimeError):
        reader.snapshot()


def test_wrong_schema_fails_closed(
    tmp_path,
):
    value = payload()
    value["schema"] = "wrong"

    write_snapshot(
        tmp_path,
        value,
    )

    reader = build(tmp_path)

    with pytest.raises(RuntimeError):
        reader.snapshot()


def test_extra_field_fails_closed(
    tmp_path,
):
    value = payload()
    value["extra"] = True

    write_snapshot(
        tmp_path,
        value,
    )

    reader = build(tmp_path)

    with pytest.raises(RuntimeError):
        reader.snapshot()


def test_duplicate_json_key_fails_closed(
    tmp_path,
):
    path = (
        tmp_path
        / "sim-native-runtime-snapshot-v2.json"
    )

    path.write_text(
        (
            '{"schema":"arms.nt.sim-runtime-readiness.v2",'
            '"schema":"arms.nt.sim-runtime-readiness.v2",'
            '"observed_at":"2026-09-27T02:29:59+00:00",'
            '"account_name":"Sim101",'
            '"provider":"Simulator",'
            '"connection_status":"Connected",'
            '"instrument":"NQ DEC26",'
            '"physical_test_readiness":"PHYSICAL_TEST_READY",'
            '"position_state":"FLAT",'
            '"active_order_count":0,'
            '"native_submit_enabled":false,'
            '"auto_retry_allowed":false}'
        ),
        encoding="utf-8",
    )

    reader = build(tmp_path)

    with pytest.raises(RuntimeError):
        reader.snapshot()


@pytest.mark.parametrize(
    "field,value",
    [
        ("account_name", "Sim102"),
        ("provider", "Continuum"),
        ("instrument", "ES DEC26"),
    ],
)
def test_identity_scope_mismatch_fails_closed(
    tmp_path,
    field,
    value,
):
    data = payload()
    data[field] = value

    write_snapshot(
        tmp_path,
        data,
    )

    reader = build(tmp_path)

    with pytest.raises(RuntimeError):
        reader.snapshot()


def test_stale_snapshot_fails_closed(
    tmp_path,
):
    write_snapshot(
        tmp_path,
        payload(
            observed_at=(
                NOW
                - timedelta(seconds=16)
            ).isoformat()
        ),
    )

    reader = build(tmp_path)

    with pytest.raises(RuntimeError):
        reader.snapshot()


def test_future_snapshot_fails_closed(
    tmp_path,
):
    write_snapshot(
        tmp_path,
        payload(
            observed_at=(
                NOW
                + timedelta(seconds=1)
            ).isoformat()
        ),
    )

    reader = build(tmp_path)

    with pytest.raises(RuntimeError):
        reader.snapshot()


def test_timestamp_must_be_utc(
    tmp_path,
):
    write_snapshot(
        tmp_path,
        payload(
            observed_at=(
                "2026-09-26T22:29:59-04:00"
            )
        ),
    )

    reader = build(tmp_path)

    with pytest.raises(RuntimeError):
        reader.snapshot()


@pytest.mark.parametrize(
    "state",
    [
        "FLAT",
        "LONG",
        "SHORT",
        "UNKNOWN",
    ],
)
def test_position_state_domain(
    tmp_path,
    state,
):
    write_snapshot(
        tmp_path,
        payload(
            position_state=state
        ),
    )

    reader = build(tmp_path)

    result = reader.snapshot()

    assert result[
        "position_state"
    ] == state


def test_invalid_position_state_fails_closed(
    tmp_path,
):
    write_snapshot(
        tmp_path,
        payload(
            position_state="MAYBE"
        ),
    )

    reader = build(tmp_path)

    with pytest.raises(RuntimeError):
        reader.snapshot()


@pytest.mark.parametrize(
    "count",
    [
        -1,
        True,
        1.5,
        "0",
    ],
)
def test_active_order_count_must_be_nonnegative_int(
    tmp_path,
    count,
):
    write_snapshot(
        tmp_path,
        payload(
            active_order_count=count
        ),
    )

    reader = build(tmp_path)

    with pytest.raises(RuntimeError):
        reader.snapshot()


def test_native_submit_must_remain_false(
    tmp_path,
):
    write_snapshot(
        tmp_path,
        payload(
            native_submit_enabled=True
        ),
    )

    reader = build(tmp_path)

    with pytest.raises(RuntimeError):
        reader.snapshot()


def test_auto_retry_must_remain_false(
    tmp_path,
):
    write_snapshot(
        tmp_path,
        payload(
            auto_retry_allowed=True
        ),
    )

    reader = build(tmp_path)

    with pytest.raises(RuntimeError):
        reader.snapshot()


def test_reader_has_no_execution_surface(
    tmp_path,
):
    reader = build(tmp_path)

    for forbidden in (
        "submit_order",
        "cancel_order",
        "modify_order",
        "close_position",
        "close_partial",
        "flatten",
        "execute",
        "consume",
        "arm",
    ):
        assert not hasattr(
            reader,
            forbidden,
        )
