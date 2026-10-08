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
    ALLOWED_BASE_SOURCES,
    CURRENT_EXPORTER_SHA256,
    EXPORTER_SHA256,
    LEGACY_EXPORTER_SHA256,
    PRIOR_EXPORTER_SHA256,
    MERGED_SOURCE,
    NATIVE_SOURCE,
    REVIEWED_EXPORTER_HASHES,
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


def october_composite():
    header, rows = native_shape(
        1,
        "2026-10-01T20:48:00Z",
        "2026-10-01",
    )
    base = native_bundle(
        header,
        rows,
    )
    bridge, seal = bridge_evidence([
        datetime(
            2026, 10, 1, 20, 49,
            tzinfo=timezone.utc,
        ),
    ])
    raw, _ = build_bundle(
        base,
        bridge,
        seal,
        SOURCE,
    )
    data = certify_bootstrap(
        raw,
        expected_sha256=sha256(raw).hexdigest(),
    )
    return raw, data


def test_productive_source_hash_and_no_execution_surface():
    normalized = SOURCE.replace(
        b"\r\n",
        b"\n",
    )

    assert (
        sha256(
            normalized.rstrip(b"\n")
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


def with_exporter_identity(raw, identity):
    bundle = json.loads(raw)
    bundle["authored_sha256"] = identity
    return json.dumps(
        bundle,
        separators=(",", ":"),
    ).encode("utf-8")


def test_current_and_reviewed_legacy_exporter_identities_are_exact():
    assert EXPORTER_SHA256 == CURRENT_EXPORTER_SHA256
    assert REVIEWED_EXPORTER_HASHES == frozenset((
        CURRENT_EXPORTER_SHA256,
        PRIOR_EXPORTER_SHA256,
        LEGACY_EXPORTER_SHA256,
    ))

    raw, _, current = certified()
    assert current.source == MERGED_SOURCE

    prior_raw = with_exporter_identity(
        raw,
        PRIOR_EXPORTER_SHA256,
    )
    prior = certify_bootstrap(
        prior_raw,
        expected_sha256=sha256(prior_raw).hexdigest(),
    )
    assert prior.sha256 != current.sha256
    assert prior.bars == current.bars
    assert prior.sessions == current.sessions
    assert prior.gap_count == current.gap_count
    assert prior.gap_report == current.gap_report
    assert prior.source == current.source

    legacy_raw = with_exporter_identity(
        raw,
        LEGACY_EXPORTER_SHA256,
    )
    legacy = certify_bootstrap(
        legacy_raw,
        expected_sha256=sha256(legacy_raw).hexdigest(),
    )
    assert legacy.sha256 != current.sha256
    assert legacy.bars == current.bars
    assert legacy.sessions == current.sessions
    assert legacy.gap_count == current.gap_count
    assert legacy.gap_report == current.gap_report
    assert legacy.source == current.source


def test_unknown_chart_catchup_exporter_identity_fails_closed():
    raw, _, _ = certified()
    unknown = with_exporter_identity(raw, "0" * 64)

    with pytest.raises(
        ValueError,
        match="CHART_CATCHUP_EXPORTER_IDENTITY",
    ):
        certify_bootstrap(
            unknown,
            expected_sha256=sha256(unknown).hexdigest(),
        )


def test_legacy_identity_does_not_authorize_forged_bundle_content():
    raw, _, _ = certified()
    bundle = json.loads(
        with_exporter_identity(
            raw,
            LEGACY_EXPORTER_SHA256,
        )
    )
    bundle["bridge_utf8"] = bundle["bridge_utf8"].replace(
        '"runtime_admission":false',
        '"runtime_admission":true',
        1,
    )
    forged = json.dumps(
        bundle,
        separators=(",", ":"),
    ).encode("utf-8")

    with pytest.raises(
        ValueError,
        match="CHART_CATCHUP_HEADER_IDENTITY",
    ):
        certify_bootstrap(
            forged,
            expected_sha256=sha256(forged).hexdigest(),
        )


def test_chainable_base_source_policy_is_exactly_two_values():
    assert ALLOWED_BASE_SOURCES == frozenset((
        NATIVE_SOURCE,
        MERGED_SOURCE,
    ))


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


def test_second_certified_catchup_retains_first_composite_and_adds_suffix():
    first_raw, first = october_composite()
    suffix = [
        datetime(2026, 10, 1, 20, minute, tzinfo=timezone.utc)
        for minute in (50, 51)
    ]
    bridge, seal = bridge_evidence(suffix)

    second_raw, result = build_bundle(
        first_raw,
        bridge,
        seal,
        SOURCE,
    )
    second = certify_bootstrap(
        second_raw,
        expected_sha256=sha256(second_raw).hexdigest(),
    )

    assert first.source == MERGED_SOURCE
    assert second.source == MERGED_SOURCE
    assert second.bars[:len(first.bars)] == first.bars
    assert second.gap_report[:len(first.gap_report)] == first.gap_report
    assert [bar.label for bar in second.bars[len(first.bars):]] == [
        "2026-10-01T20:50:00.0000000Z",
        "2026-10-01T20:51:00.0000000Z",
    ]
    labels = [bar.label for bar in second.bars]
    assert labels == sorted(labels)
    assert len(labels) == len(set(labels))
    assert result["bars"] == len(first.bars) + len(suffix)
    assert all(
        bar.low <= min(bar.open, bar.close)
        <= max(bar.open, bar.close) <= bar.high
        and bar.volume >= 0
        for bar in second.bars
    )

    outer = json.loads(second_raw)
    rows = [json.loads(line) for line in outer["bridge_utf8"].splitlines()]
    assert rows[0]["runtime_admission"] is False
    assert rows[0]["execution_authority"] is False
    seal_row = json.loads(outer["seal_utf8"])
    assert seal_row["runtime_admission"] is False
    assert seal_row["execution_authority"] is False


@pytest.mark.parametrize(
    "fault",
    (
        "inner_base_bytes",
        "inner_base_sha",
        "nested_chart_evidence",
    ),
)
def test_second_certified_catchup_rejects_tampered_inner_evidence(fault):
    first_raw, _ = october_composite()
    bridge, seal = bridge_evidence([
        datetime(2026, 10, 1, 20, 50, tzinfo=timezone.utc),
    ])
    second_raw, _ = build_bundle(
        first_raw,
        bridge,
        seal,
        SOURCE,
    )
    outer = json.loads(second_raw)
    inner = json.loads(outer["base_utf8"])

    if fault == "inner_base_bytes":
        inner["base_utf8"] += " "
    elif fault == "inner_base_sha":
        inner["base_sha256"] = "0" * 64
    else:
        inner["bridge_utf8"] = inner["bridge_utf8"].replace(
            '"runtime_admission":false',
            '"runtime_admission":true',
            1,
        )

    tampered_inner = json.dumps(
        inner,
        separators=(",", ":"),
    )
    outer["base_utf8"] = tampered_inner
    outer["base_sha256"] = sha256(
        tampered_inner.encode("utf-8")
    ).hexdigest()
    tampered = json.dumps(
        outer,
        separators=(",", ":"),
    ).encode("utf-8")

    with pytest.raises(ValueError):
        certify_bootstrap(
            tampered,
            expected_sha256=sha256(tampered).hexdigest(),
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
        match="UNEXPECTED_DATA_GAP",
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
