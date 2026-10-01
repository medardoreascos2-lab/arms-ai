"""Synthetic chart catch-up certification only; never starts NinjaTrader."""
from copy import deepcopy
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

import pytest

from backend.market_data.certified_bootstrap_v1 import (
    certify_bootstrap,
)
from backend.market_data.chart_catchup_bridge_v1 import (
    EXPORTER_SHA256,
    MERGED_SOURCE,
)
from backend.tests.test_native_historical_bootstrap_sprint16a import (
    bundle as native_bundle,
    native_shape,
)
from backend.tests.test_analysis_time_sprint15x import (
    encode,
    stamp,
)
from tools.certify_chart_catchup_v1 import (
    build_bundle,
)

SOURCE = Path(
    "integrations/ninjatrader/"
    "ArmsChartCatchupBridgeV1.cs"
).read_bytes()


def raw_unspecified(
    value,
):
    return stamp(value).removesuffix(
        "Z"
    )


def bridge_evidence(
    labels,
    *,
    mutate=None,
    latest_closed=False,
):
    run_id = str(
        uuid4()
    )

    rows = [
        {
            "schema":
                "arms.nt.chart-catchup.header.v1",
            "run_id":
                run_id,
            "exporter":
                "ArmsChartCatchupBridgeV1/1",
            "source":
                "NINJATRADER_LOADED_CHART_BARS",
            "provider":
                "Provider31",
            "instrument":
                "NQ",
            "contract":
                "NQ DEC26",
            "expiry":
                "2026-12-01",
            "bars_type":
                "Minute",
            "bars_value":
                1,
            "timeframe":
                "1m",
            "trading_hours":
                "CME US Index Futures ETH",
            "application_timezone":
                "UTC",
            "bar_label":
                "CLOSE",
            "tick_size":
                .25,
            "point_value":
                20,
            "requested_from_close":
                stamp(labels[0]),
            "configured_through_close":
                (
                    "LATEST_CLOSED"
                    if latest_closed
                    else stamp(
                        labels[-1]
                    )
                ),
            "through_selection":
                (
                    "CHART_LATEST_CLOSED"
                    if latest_closed
                    else "EXPLICIT_UTC"
                ),
            "requested_through_close":
                stamp(labels[-1]),
            "chart_bar_count":
                (
                    5000
                    + len(labels)
                    + 1
                    if latest_closed
                    else 10000
                ),
            "excluded_last":
                True,
            "raw_time_kind":
                "Unspecified",
            "classification":
                "CHART_CATCHUP",
            "observation_only":
                True,
            "runtime_admission":
                False,
            "execution_authority":
                False,
        }
    ]

    from tools.native_timing_witness_v1 import (
        ticks,
    )

    for index, label in enumerate(
        labels
    ):
        explicit = stamp(label)

        value = 20000 + index * .25

        rows.append(
            {
                "schema":
                    "arms.nt.chart-catchup.bar.v1",
                "run_id":
                    run_id,
                "index":
                    index,
                "chart_index":
                    5000 + index,
                "raw_time":
                    raw_unspecified(
                        label
                    ),
                "raw_time_kind":
                    "Unspecified",
                "raw_ticks":
                    ticks(
                        explicit
                    ),
                "bar_time":
                    explicit,
                "open":
                    value,
                "high":
                    value + 1,
                "low":
                    value - 1,
                "close":
                    value + .25,
                "volume":
                    10,
                "classification":
                    "CHART_CATCHUP",
                "observation_only":
                    True,
                "runtime_admission":
                    False,
                "execution_authority":
                    False,
            }
        )

    if mutate:
        mutate(rows)

    body = (
        b"\n".join(
            encode(row)
            for row in rows
        )
        + b"\n"
    )

    seal = encode(
        {
            "schema":
                "arms.nt.chart-catchup.seal.v1",
            "run_id":
                run_id,
            "bytes":
                len(body),
            "records":
                len(rows),
            "bars":
                len(labels),
            "sha256":
                sha256(
                    body
                ).hexdigest(),
            "writer_closed":
                True,
            "complete":
                True,
            "classification":
                "CHART_CATCHUP",
            "runtime_admission":
                False,
            "execution_authority":
                False,
        }
    )

    return body, seal


def base_raw():
    header, rows = native_shape(
        2,
        "2026-09-21T20:58:00Z",
        "2026-09-21",
    )

    return native_bundle(
        header,
        rows,
    )


def successful_labels():
    return [
        datetime(
            2026,
            9,
            21,
            21,
            0,
            tzinfo=timezone.utc,
        ),
        datetime(
            2026,
            9,
            21,
            22,
            1,
            tzinfo=timezone.utc,
        ),
        datetime(
            2026,
            9,
            21,
            22,
            2,
            tzinfo=timezone.utc,
        ),
    ]


def certified():
    base = base_raw()

    bridge, seal = bridge_evidence(
        successful_labels()
    )

    raw, result = build_bundle(
        base,
        bridge,
        seal,
        SOURCE,
    )

    data = certify_bootstrap(
        raw,
        expected_sha256=
            sha256(raw).hexdigest(),
    )

    return raw, result, data


def test_productive_source_hash_and_no_execution_surface():
    normalized = SOURCE.replace(
        b"\r\n",
        b"\n",
    )

    assert (
        sha256(
            normalized
        ).hexdigest()
        == EXPORTER_SHA256
    )

    text = normalized.decode(
        "utf-8"
    )

    for forbidden in (
        "CreateOrder(",
        "SubmitOrder",
        "ChangeOrder",
        "CancelOrder",
        "Account.All",
        "AtmStrategy",
        "EnterLong",
        "EnterShort",
    ):
        assert forbidden not in text

    assert (
        "runtime_admission ="
        in text
    )

    assert (
        "execution_authority ="
        in text
    )


def test_bridge_extends_certified_bootstrap_and_dispatches():
    raw, result, data = certified()

    assert (
        data.source
        == MERGED_SOURCE
    )

    assert len(
        data.bars
    ) == 5

    assert (
        data.bars[-1].label
        == "2026-09-21T22:02:00.0000000Z"
    )

    assert (
        data.gap_count
        == 1
    )

    assert (
        data.gap_report[-1][2]
        == "EXPECTED_SESSION_GAP"
    )

    assert (
        result["bars"]
        == 5
    )

    assert (
        sha256(raw).hexdigest()
        == data.sha256
    )




def test_latest_closed_mode_is_bound_to_chart_count_minus_two():
    base = base_raw()

    bridge, seal = bridge_evidence(
        successful_labels(),
        latest_closed=True,
    )

    raw, result = build_bundle(
        base,
        bridge,
        seal,
        SOURCE,
    )

    data = certify_bootstrap(
        raw,
        expected_sha256=
            sha256(raw).hexdigest(),
    )

    assert (
        data.source
        == MERGED_SOURCE
    )

    assert (
        data.bars[-1].label
        == "2026-09-21T22:02:00.0000000Z"
    )

    assert (
        result["bars"]
        == 5
    )


def test_latest_closed_mode_rejects_nonlatest_chart_row():
    base = base_raw()

    def mutate(rows):
        rows[0][
            "chart_bar_count"
        ] += 1

    bridge, seal = bridge_evidence(
        successful_labels(),
        latest_closed=True,
        mutate=mutate,
    )

    with pytest.raises(
        ValueError,
        match=
            "CHART_CATCHUP_LATEST_CLOSED_PROOF",
    ):
        build_bundle(
            base,
            bridge,
            seal,
            SOURCE,
        )


def test_latest_closed_mode_rejects_configuration_substitution():
    base = base_raw()

    def mutate(rows):
        rows[0][
            "configured_through_close"
        ] = (
            "2026-09-21T22:02:00Z"
        )

    bridge, seal = bridge_evidence(
        successful_labels(),
        latest_closed=True,
        mutate=mutate,
    )

    with pytest.raises(
        ValueError,
        match=
            "CHART_CATCHUP_LATEST_CLOSED_CONFIGURATION",
    ):
        build_bundle(
            base,
            bridge,
            seal,
            SOURCE,
        )


def test_missing_open_minute_fails_closed():
    labels = successful_labels()

    labels[-1] = (
        labels[-1]
        + timedelta(
            minutes=1
        )
    )

    bridge, seal = bridge_evidence(
        labels
    )

    with pytest.raises(
        ValueError,
    ):
        build_bundle(
            base_raw(),
            bridge,
            seal,
            SOURCE,
        )


def test_tick_movement_fails_closed():
    def mutate(rows):
        rows[1][
            "raw_ticks"
        ] += 1

    bridge, seal = bridge_evidence(
        successful_labels(),
        mutate=mutate,
    )

    # Seal must describe the mutated body.
    decoded = [
        json.loads(line)
        for line in bridge.decode(
            "utf-8"
        ).splitlines()
    ]

    assert (
        decoded[1][
            "raw_ticks"
        ]
        % 10
        != 0
    )

    with pytest.raises(
        ValueError,
    ):
        build_bundle(
            base_raw(),
            bridge,
            seal,
            SOURCE,
        )


def test_clock_field_relabel_fails_closed():
    def mutate(rows):
        rows[1][
            "bar_time"
        ] = (
            "2026-09-21T21:01:00.0000000Z"
        )

    bridge, seal = bridge_evidence(
        successful_labels(),
        mutate=mutate,
    )

    with pytest.raises(
        ValueError,
    ):
        build_bundle(
            base_raw(),
            bridge,
            seal,
            SOURCE,
        )


def test_ohlcv_mutation_fails_closed():
    def mutate(rows):
        rows[1]["low"] = 30000

    bridge, seal = bridge_evidence(
        successful_labels(),
        mutate=mutate,
    )

    with pytest.raises(
        ValueError,
    ):
        build_bundle(
            base_raw(),
            bridge,
            seal,
            SOURCE,
        )


def test_wrong_source_fails_closed():
    bridge, seal = bridge_evidence(
        successful_labels()
    )

    with pytest.raises(
        ValueError,
        match="CHART_CATCHUP_EXPORTER_SOURCE_CHANGED",
    ):
        build_bundle(
            base_raw(),
            bridge,
            seal,
            b"not reviewed",
        )


def test_outer_pin_is_mandatory():
    raw, _, _ = certified()

    with pytest.raises(
        ValueError,
        match="BOOTSTRAP_PIN_MISMATCH",
    ):
        certify_bootstrap(
            raw,
            expected_sha256=
                "0" * 64,
        )
