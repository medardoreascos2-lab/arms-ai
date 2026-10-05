"""Certified loaded-chart catch-up extension for a pinned native bootstrap.

This module grants no current-time, session, news or execution authority.
The bridge can only extend a previously certified bootstrap using immutable
loaded-chart observations whose clock fields are proven tick-preserving and
whose every missing minute is justified by the pinned native calendar.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re

from backend.market_data.certified_bootstrap_v1 import (
    BootstrapBar,
    CertifiedBootstrap,
    MAX_BARS,
    require,
)
from tools.native_timing_witness_v1 import (
    parse,
    ticks,
    MINUTE as MINUTE_TICKS,
)

SCHEMA = "arms.certified-chart-catchup.v1"
EXPORTER_SHA256 = "61696d2d0b34869585f639ec6643acfb20dd4db1c9cdad1210bdb5ea9773fd57"

SOURCE = "NINJATRADER_LOADED_CHART_BARS"
NATIVE_SOURCE = "NATIVE_HISTORICAL_REPOSITORY"
MERGED_SOURCE = (
    NATIVE_SOURCE
    + "+NINJATRADER_LOADED_CHART_BARS"
)
ALLOWED_BASE_SOURCES = frozenset((
    NATIVE_SOURCE,
    MERGED_SOURCE,
))

MINUTE = timedelta(minutes=1)
MAX_BRIDGE_BYTES = 16 * 1024 * 1024
MAX_BRIDGE_BARS = 3000

HEADER_FIELDS = {
    "schema",
    "run_id",
    "exporter",
    "source",
    "provider",
    "instrument",
    "contract",
    "expiry",
    "bars_type",
    "bars_value",
    "timeframe",
    "trading_hours",
    "application_timezone",
    "bar_label",
    "tick_size",
    "point_value",
    "requested_from_close",
    "configured_through_close",
    "through_selection",
    "requested_through_close",
    "chart_bar_count",
    "excluded_last",
    "raw_time_kind",
    "classification",
    "observation_only",
    "runtime_admission",
    "execution_authority",
}

BAR_FIELDS = {
    "schema",
    "run_id",
    "index",
    "chart_index",
    "raw_time",
    "raw_time_kind",
    "raw_ticks",
    "bar_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "classification",
    "observation_only",
    "runtime_admission",
    "execution_authority",
}

SEAL_FIELDS = {
    "schema",
    "run_id",
    "bytes",
    "records",
    "bars",
    "sha256",
    "writer_closed",
    "complete",
    "classification",
    "runtime_admission",
    "execution_authority",
}


def _lines(value):
    require(
        type(value) is str,
        "CHART_CATCHUP_RAW_TYPE",
    )

    raw = value.encode("utf-8")

    require(
        0 < len(raw) <= MAX_BRIDGE_BYTES
        and raw.endswith(b"\n"),
        "CHART_CATCHUP_TRUNCATED",
    )

    rows = raw.split(b"\n")[:-1]

    require(
        2 <= len(rows)
        <= MAX_BRIDGE_BARS + 1,
        "CHART_CATCHUP_RECORD_LIMIT",
    )

    require(
        all(
            0 < len(row) <= 16384
            and b"\r" not in row
            for row in rows
        ),
        "CHART_CATCHUP_LINE_LIMIT",
    )

    return raw, rows


def _dotnet_ticks_from_clock_text(
    value,
    kind,
):
    require(
        type(value) is str
        and kind in {
            "Utc",
            "Unspecified",
        },
        "CHART_CATCHUP_RAW_TIME",
    )

    if kind == "Utc":
        match = re.fullmatch(
            r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)"
            r"\.(\d{7})Z",
            value,
        )
    else:
        match = re.fullmatch(
            r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)"
            r"\.(\d{7})",
            value,
        )

    require(
        match is not None,
        "CHART_CATCHUP_RAW_TIME_ENCODING",
    )

    instant = datetime.fromisoformat(
        match.group(1)
    )

    epoch = datetime(
        1,
        1,
        1,
    )

    delta = instant - epoch

    return (
        (
            delta.days * 86400
            + delta.seconds
        )
        * 10_000_000
        + int(
            match.group(2)
        )
    )


def _explicit_utc(
    raw_time,
    raw_kind,
):
    _dotnet_ticks_from_clock_text(
        raw_time,
        raw_kind,
    )

    return (
        raw_time
        if raw_kind == "Utc"
        else raw_time + "Z"
    )


def certify_chart_catchup_bundle(
    bundle,
    digest,
):
    require(
        set(bundle)
        == {
            "schema",
            "authored_sha256",
            "base_sha256",
            "base_utf8",
            "bridge_utf8",
            "seal_utf8",
        }
        and bundle["schema"] == SCHEMA,
        "CHART_CATCHUP_BUNDLE_SCHEMA",
    )

    require(
        bundle["authored_sha256"]
        == EXPORTER_SHA256,
        "CHART_CATCHUP_EXPORTER_IDENTITY",
    )

    require(
        type(bundle["base_utf8"])
        is str
        and type(bundle["base_sha256"])
        is str,
        "CHART_CATCHUP_BASE_SCHEMA",
    )

    base_raw = bundle[
        "base_utf8"
    ].encode("utf-8")

    require(
        sha256(
            base_raw
        ).hexdigest()
        == bundle["base_sha256"],
        "CHART_CATCHUP_BASE_PIN",
    )

    from backend.market_data.certified_bootstrap_v1 import (
        certify_bootstrap,
    )

    base = certify_bootstrap(
        base_raw,
        expected_sha256=
            bundle["base_sha256"],
    )

    require(
        base.source
        in ALLOWED_BASE_SOURCES,
        "CHART_CATCHUP_BASE_SOURCE",
    )

    bridge_raw, lines = _lines(
        bundle["bridge_utf8"]
    )

    header = parse(
        lines[0]
    )

    require(
        set(header)
        == HEADER_FIELDS
        and header["schema"]
        == "arms.nt.chart-catchup.header.v1",
        "CHART_CATCHUP_HEADER_SCHEMA",
    )

    expected_header = {
        "exporter":
            "ArmsChartCatchupBridgeV1/1",
        "source":
            SOURCE,
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
            0.25,
        "point_value":
            20,
        "excluded_last":
            True,
        "classification":
            "CHART_CATCHUP",
        "observation_only":
            True,
        "runtime_admission":
            False,
        "execution_authority":
            False,
    }

    require(
        all(
            type(header.get(key))
            is type(value)
            and header.get(key)
            == value
            for key, value
            in expected_header.items()
        ),
        "CHART_CATCHUP_HEADER_IDENTITY",
    )

    from uuid import UUID

    run_id = header[
        "run_id"
    ]

    require(
        type(run_id) is str
        and str(
            UUID(run_id)
        ) == run_id,
        "CHART_CATCHUP_RUN_ID",
    )

    require(
        type(header["chart_bar_count"])
        is int
        and header["chart_bar_count"]
        >= len(lines),
        "CHART_CATCHUP_CHART_COUNT",
    )

    raw_kind = header[
        "raw_time_kind"
    ]

    require(
        raw_kind
        in {
            "Utc",
            "Unspecified",
        },
        "CHART_CATCHUP_RAW_KIND",
    )

    requested_from = header[
        "requested_from_close"
    ]

    configured_through = header[
        "configured_through_close"
    ]

    through_selection = header[
        "through_selection"
    ]

    requested_through = header[
        "requested_through_close"
    ]

    require(
        type(configured_through)
        is str
        and through_selection
        in {
            "EXPLICIT_UTC",
            "CHART_LATEST_CLOSED",
        },
        "CHART_CATCHUP_THROUGH_SELECTION",
    )

    from_close = datetime.fromisoformat(
        requested_from.replace(
            "Z",
            "+00:00",
        )
    )

    through_close = datetime.fromisoformat(
        requested_through.replace(
            "Z",
            "+00:00",
        )
    )

    require(
        from_close.tzinfo
        is not None
        and through_close.tzinfo
        is not None
        and from_close.utcoffset()
        == timedelta(0)
        and through_close.utcoffset()
        == timedelta(0)
        and from_close <= through_close
        and through_close - from_close
        <= timedelta(days=2),
        "CHART_CATCHUP_REQUEST_RANGE",
    )

    if (
        through_selection
        == "EXPLICIT_UTC"
    ):
        configured_close = (
            datetime.fromisoformat(
                configured_through.replace(
                    "Z",
                    "+00:00",
                )
            )
        )

        require(
            configured_close.tzinfo
            is not None
            and configured_close.utcoffset()
            == timedelta(0)
            and configured_close
            == through_close,
            "CHART_CATCHUP_EXPLICIT_THROUGH",
        )

    else:
        require(
            configured_through
            == "LATEST_CLOSED",
            "CHART_CATCHUP_LATEST_CLOSED_CONFIGURATION",
        )

    bars = []

    chart_indexes = []

    gaps = []

    previous_label = None

    for index, raw in enumerate(
        lines[1:]
    ):
        row = parse(raw)

        require(
            set(row)
            == BAR_FIELDS
            and row["schema"]
            == "arms.nt.chart-catchup.bar.v1",
            "CHART_CATCHUP_BAR_SCHEMA",
        )

        require(
            row["run_id"]
            == run_id
            and type(row["index"])
            is int
            and row["index"] == index
            and type(row["chart_index"])
            is int,
            "CHART_CATCHUP_BAR_IDENTITY",
        )

        require(
            row["raw_time_kind"]
            == raw_kind,
            "CHART_CATCHUP_MIXED_RAW_KIND",
        )

        raw_ticks = (
            _dotnet_ticks_from_clock_text(
                row["raw_time"],
                row["raw_time_kind"],
            )
        )

        require(
            type(row["raw_ticks"])
            is int
            and row["raw_ticks"]
            == raw_ticks,
            "CHART_CATCHUP_RAW_TICKS",
        )

        explicit = _explicit_utc(
            row["raw_time"],
            row["raw_time_kind"],
        )

        require(
            row["bar_time"]
            == explicit,
            "CHART_CATCHUP_CLOCK_FIELDS_MOVED",
        )

        require(
            ticks(
                row["bar_time"]
            )
            % MINUTE_TICKS
            == 0,
            "CHART_CATCHUP_MINUTE_LABEL",
        )

        require(
            row["classification"]
            == "CHART_CATCHUP"
            and row["observation_only"]
            is True
            and row["runtime_admission"]
            is False
            and row["execution_authority"]
            is False,
            "CHART_CATCHUP_BAR_AUTHORITY",
        )

        chart_indexes.append(
            row["chart_index"]
        )

        payload = {
            key: row[key]
            for key in (
                "bar_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
            )
        }

        from backend.market_data.certified_bootstrap_v1 import (
            _bar,
        )

        bar = _bar(payload)

        label = datetime.fromisoformat(
            bar.label.replace(
                "Z",
                "+00:00",
            )
        )

        require(
            from_close <= label
            <= through_close,
            "CHART_CATCHUP_BAR_OUTSIDE_REQUEST",
        )

        require(
            base.calendar_coverage
            and base.calendar_coverage[0]
            <= label
            <= base.calendar_coverage[1],
            "CHART_CATCHUP_OUTSIDE_CALENDAR_COVERAGE",
        )

        require(
            any(
                start
                <= label - MINUTE
                and label <= stop
                for start, stop, _
                in base.calendar_intervals
            ),
            "CHART_CATCHUP_BAR_OUTSIDE_SESSION",
        )

        if previous_label is not None:
            from backend.market_data.native_historical_bootstrap_v1 import (
                classify_gap,
            )

            status = classify_gap(
                previous_label,
                label,
                base.calendar_intervals,
                base.calendar_coverage,
            )

            require(
                status
                in {
                    "CONTIGUOUS",
                    "EXPECTED_SESSION_GAP",
                },
                status,
            )

            if (
                status
                != "CONTIGUOUS"
            ):
                gaps.append(
                    (
                        bars[-1].label,
                        bar.label,
                        status,
                        int(
                            (
                                label
                                - previous_label
                            )
                            / MINUTE
                        ) - 1,
                    )
                )

        bars.append(bar)

        previous_label = label

    require(
        0 < len(bars)
        <= MAX_BRIDGE_BARS,
        "CHART_CATCHUP_EMPTY",
    )

    require(
        all(
            b > a
            for a, b
            in zip(
                chart_indexes,
                chart_indexes[1:],
            )
        ),
        "CHART_CATCHUP_CHART_INDEX_ORDER",
    )

    require(
        bars[0].label
        == requested_from
        and bars[-1].label
        == requested_through,
        "CHART_CATCHUP_REQUEST_BOUNDARY",
    )

    if (
        through_selection
        == "CHART_LATEST_CLOSED"
    ):
        require(
            chart_indexes[-1]
            == header[
                "chart_bar_count"
            ] - 2,
            "CHART_CATCHUP_LATEST_CLOSED_PROOF",
        )

    base_last = datetime.fromisoformat(
        base.bars[-1].label.replace(
            "Z",
            "+00:00",
        )
    )

    first = datetime.fromisoformat(
        bars[0].label.replace(
            "Z",
            "+00:00",
        )
    )

    from backend.market_data.native_historical_bootstrap_v1 import (
        classify_gap,
    )

    boundary_status = classify_gap(
        base_last,
        first,
        base.calendar_intervals,
        base.calendar_coverage,
    )

    require(
        boundary_status
        in {
            "CONTIGUOUS",
            "EXPECTED_SESSION_GAP",
        },
        "CHART_CATCHUP_BASE_BOUNDARY",
    )

    if (
        boundary_status
        != "CONTIGUOUS"
    ):
        gaps.insert(
            0,
            (
                base.bars[-1].label,
                bars[0].label,
                boundary_status,
                int(
                    (
                        first
                        - base_last
                    )
                    / MINUTE
                ) - 1,
            ),
        )

    seal_raw = bundle[
        "seal_utf8"
    ]

    require(
        type(seal_raw) is str
        and 0 < len(seal_raw)
        <= 4096,
        "CHART_CATCHUP_SEAL_SIZE",
    )

    seal = parse(
        seal_raw.encode(
            "utf-8"
        )
    )

    require(
        set(seal)
        == SEAL_FIELDS,
        "CHART_CATCHUP_SEAL_FIELDS",
    )

    expected_seal = {
        "schema":
            "arms.nt.chart-catchup.seal.v1",
        "run_id":
            run_id,
        "bytes":
            len(bridge_raw),
        "records":
            len(lines),
        "bars":
            len(bars),
        "sha256":
            sha256(
                bridge_raw
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

    require(
        all(
            type(seal.get(key))
            is type(value)
            and seal.get(key)
            == value
            for key, value
            in expected_seal.items()
        ),
        "CHART_CATCHUP_SEAL_INTEGRITY",
    )

    merged_bars = (
        tuple(base.bars)
        + tuple(bars)
    )

    require(
        len(merged_bars)
        <= MAX_BARS,
        "CHART_CATCHUP_TOTAL_BAR_LIMIT",
    )

    merged_gaps = (
        tuple(
            base.gap_report
        )
        + tuple(gaps)
    )

    return CertifiedBootstrap(
        digest,
        merged_bars,
        tuple(base.sessions)
        + (run_id,),
        len(merged_gaps),
        source=MERGED_SOURCE,
        calendar_intervals=
            base.calendar_intervals,
        calendar_coverage=
            base.calendar_coverage,
        gap_report=
            merged_gaps,
    )
