"""Fresh startup chart catch-up coordination.

Creates an empty operator-controlled capture directory, produces only
configuration metadata outside that directory, and certifies exactly one
sealed ArmsChartCatchupBridgeV1 capture against a pinned native base.

It never starts NinjaTrader, never arms the live adapter and has no
account/order interface.
"""
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from hashlib import sha256
import json
from pathlib import Path
import time

from backend.market_data.analysis_time_profile_v1 import (
    require,
)
from backend.market_data.certified_bootstrap_v1 import (
    CertifiedBootstrap,
    certify_bootstrap,
)
from backend.market_data.chart_catchup_bridge_v1 import (
    ALLOWED_BASE_SOURCES,
    MERGED_SOURCE,
)
from backend.market_data.chart_catchup_source_identity_v1 import (
    verify_chart_catchup_source,
)
from backend.market_data.fresh_native_adapter_v1 import (
    local_path,
)
from tools.certify_analysis_bootstrap_v1 import (
    bounded_read,
)
from tools.certify_chart_catchup_v1 import (
    build_bundle,
)
from tools.production_timing_v1 import (
    parse,
)


REQUEST_SCHEMA = (
    "arms.startup-chart-catchup-request.v1"
)

MINUTE = timedelta(
    minutes=1
)


def _utc(value):
    require(
        isinstance(
            value,
            datetime,
        )
        and value.tzinfo
        is not None
        and value.utcoffset()
        == timedelta(0),
        "STARTUP_CATCHUP_UTC_REQUIRED",
    )

    return value.astimezone(
        timezone.utc
    )


def _floor_minute(value):
    value = _utc(value)

    return value.replace(
        second=0,
        microsecond=0,
    )


def _parse_label(value):
    require(
        type(value) is str
        and value.endswith("Z"),
        "STARTUP_CATCHUP_LABEL",
    )

    try:
        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        raise ValueError(
            "STARTUP_CATCHUP_LABEL"
        ) from None

    return _utc(parsed)


def _request_text(value):
    value = _floor_minute(value)

    return value.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def next_expected_close(
    bootstrap,
):
    require(
        type(bootstrap)
        is CertifiedBootstrap
        and bootstrap.source
        in ALLOWED_BASE_SOURCES
        and bool(bootstrap.bars)
        and bool(
            bootstrap.calendar_intervals
        ),
        "STARTUP_CATCHUP_NATIVE_BASE_REQUIRED",
    )

    last = _parse_label(
        bootstrap.bars[-1].label
    )

    for start, stop, _ in (
        bootstrap.calendar_intervals
    ):
        start = _utc(start)
        stop = _utc(stop)

        if stop <= last:
            continue

        candidate = max(
            last + MINUTE,
            start + MINUTE,
        )

        candidate = _floor_minute(
            candidate
        )

        if candidate <= stop:
            return candidate

    raise ValueError(
        "STARTUP_CATCHUP_NO_NEXT_CLOSE"
    )


def latest_expected_close(
    bootstrap,
    now_utc,
):
    limit = _floor_minute(
        now_utc
    )

    best = None

    for start, stop, _ in (
        bootstrap.calendar_intervals
    ):
        start = _utc(start)
        stop = _utc(stop)

        first_close = (
            start + MINUTE
        )

        if first_close > limit:
            continue

        candidate = min(
            stop,
            limit,
        )

        candidate = _floor_minute(
            candidate
        )

        if candidate < first_close:
            continue

        if (
            best is None
            or candidate > best
        ):
            best = candidate

    require(
        best is not None,
        "STARTUP_CATCHUP_NO_THROUGH_CLOSE",
    )

    return best


def prepare_request(
    run_directory,
    bootstrap,
    *,
    now_utc=None,
    latest_closed=False,
):
    require(
        type(latest_closed)
        is bool,
        "STARTUP_CATCHUP_LATEST_CLOSED_FLAG",
    )

    run_directory = local_path(
        Path(run_directory).resolve()
    )

    require(
        run_directory.is_dir(),
        "STARTUP_CATCHUP_RUN_DIRECTORY",
    )

    now_utc = (
        datetime.now(
            timezone.utc
        )
        if now_utc is None
        else now_utc
    )

    from_close = (
        next_expected_close(
            bootstrap
        )
    )

    through_close = (
        latest_expected_close(
            bootstrap,
            now_utc,
        )
    )

    require(
        from_close <= through_close,
        "STARTUP_CATCHUP_BASE_NOT_BEHIND",
    )

    require(
        through_close - from_close
        <= timedelta(days=2),
        "STARTUP_CATCHUP_RANGE_LIMIT",
    )

    live_output_directory = (
        run_directory
        / "inbox"
    )

    capture = (
        run_directory
        / "chart-catchup"
    )

    request_path = (
        run_directory
        / "chart-catchup-request.json"
    )

    require(
        not capture.exists()
        and not request_path.exists(),
        "STARTUP_CATCHUP_REQUEST_REENTRY",
    )

    capture.mkdir(
        exist_ok=False
    )

    require(
        not any(
            capture.iterdir()
        ),
        "STARTUP_CATCHUP_CAPTURE_NOT_EMPTY",
    )

    request = {
        "schema":
            REQUEST_SCHEMA,
        "indicator":
            "ArmsChartCatchupBridgeV1",
        "capture_enabled":
            True,
        "output_directory":
            str(capture),
        "live_output_directory":
            str(live_output_directory),
        "expected_provider_enum":
            "Provider31",
        "from_close_utc":
            _request_text(
                from_close
            ),
        "through_close_utc":
            (
                "LATEST_CLOSED"
                if latest_closed
                else _request_text(
                    through_close
                )
            ),
        "through_selection":
            (
                "CHART_LATEST_CLOSED"
                if latest_closed
                else
                "HOST_UTC_OPERATIONAL_HINT_CLIPPED_TO_REVIEWED_SESSION"
            ),
        "absolute_time_authority":
            "NONE",
        "observation_only":
            True,
        "runtime_admission":
            False,
        "execution_authority":
            False,
    }

    raw = json.dumps(
        request,
        indent=2,
        sort_keys=True,
    ).encode(
        "utf-8"
    )

    with request_path.open(
        "xb"
    ) as handle:
        handle.write(raw)

    require(
        not any(
            capture.iterdir()
        ),
        "STARTUP_CATCHUP_CAPTURE_DIRTY_AFTER_REQUEST",
    )

    return request


def capture_status(
    capture_directory,
):
    """Return the only accepted productive writer lifecycle state."""
    capture = local_path(
        Path(
            capture_directory
        ).resolve()
    )

    require(
        capture.is_dir(),
        "STARTUP_CATCHUP_CAPTURE_DIRECTORY",
    )

    entries = list(
        capture.iterdir()
    )

    require(
        all(
            path.is_file()
            for path in entries
        ),
        "STARTUP_CATCHUP_EVIDENCE_FILE_SET",
    )

    bodies = [
        path
        for path in entries
        if path.name.endswith(
            ".chart-catchup.jsonl"
        )
    ]

    seals = [
        path
        for path in entries
        if path.name.endswith(
            ".chart-catchup.jsonl.done.json"
        )
    ]

    temporaries = [
        path
        for path in entries
        if path.name.endswith(
            ".chart-catchup.jsonl.done.tmp"
        )
    ]

    allowed = set(
        bodies
        + seals
        + temporaries
    )

    require(
        set(entries)
        == allowed,
        "STARTUP_CATCHUP_UNEXPECTED_FILE",
    )

    require(
        len(bodies) <= 1
        and len(seals) <= 1
        and len(temporaries) <= 1,
        "STARTUP_CATCHUP_SESSION_ROTATION",
    )

    if seals:
        require(
            len(bodies) == 1
            and not temporaries
            and seals[0]
            == Path(
                str(bodies[0])
                + ".done.json"
            ),
            "STARTUP_CATCHUP_FINAL_SEAL_STATE",
        )

        return "READY"

    if temporaries:
        require(
            len(bodies) == 1
            and temporaries[0]
            == Path(
                str(bodies[0])
                + ".done.tmp"
            ),
            "STARTUP_CATCHUP_TEMP_SEAL_STATE",
        )

        return "SEALING"

    if bodies:
        return "BODY_WRITTEN"

    return "WAITING"


def await_capture(
    capture_directory,
    *,
    timeout_seconds,
    guard,
    poll_seconds=.25,
    monotonic=time.monotonic,
    sleeper=time.sleep,
):
    """Wait only for a valid sealed capture while external health stays green."""
    require(
        type(timeout_seconds)
        in {
            int,
            float,
        }
        and 0
        < timeout_seconds
        <= 900,
        "STARTUP_CATCHUP_TIMEOUT_BUDGET",
    )

    require(
        type(poll_seconds)
        in {
            int,
            float,
        }
        and 0
        < poll_seconds
        <= 1,
        "STARTUP_CATCHUP_POLL_BUDGET",
    )

    require(
        callable(guard)
        and callable(monotonic)
        and callable(sleeper),
        "STARTUP_CATCHUP_WATCHER_CALLBACK",
    )

    deadline = (
        monotonic()
        + timeout_seconds
    )

    previous = None

    ordering = {
        "WAITING": 0,
        "BODY_WRITTEN": 1,
        "SEALING": 2,
        "READY": 3,
    }

    while True:
        guard()

        status = capture_status(
            capture_directory
        )

        require(
            status in ordering,
            "STARTUP_CATCHUP_CAPTURE_STATUS",
        )

        if previous is not None:
            require(
                ordering[status]
                >= ordering[previous],
                "STARTUP_CATCHUP_CAPTURE_REGRESSION",
            )

        previous = status

        if status == "READY":
            return status

        require(
            monotonic()
            < deadline,
            "STARTUP_CATCHUP_CAPTURE_TIMEOUT",
        )

        sleeper(
            poll_seconds
        )


def _capture_files(
    capture_directory,
):
    capture = local_path(
        Path(
            capture_directory
        ).resolve()
    )

    require(
        capture.is_dir(),
        "STARTUP_CATCHUP_CAPTURE_DIRECTORY",
    )

    require(
        capture_status(
            capture
        )
        == "READY",
        "STARTUP_CATCHUP_NOT_READY",
    )

    entries = list(
        capture.iterdir()
    )

    require(
        entries
        and all(
            path.is_file()
            for path in entries
        ),
        "STARTUP_CATCHUP_EVIDENCE_FILE_SET",
    )

    bodies = [
        path
        for path in entries
        if path.name.endswith(
            ".chart-catchup.jsonl"
        )
    ]

    seals = [
        path
        for path in entries
        if path.name.endswith(
            ".chart-catchup.jsonl.done.json"
        )
    ]

    require(
        len(bodies) == 1
        and len(seals) == 1,
        "STARTUP_CATCHUP_EVIDENCE_COUNT",
    )

    body = bodies[0]
    seal = seals[0]

    require(
        seal
        == Path(
            str(body)
            + ".done.json"
        ),
        "STARTUP_CATCHUP_SEAL_NAME",
    )

    require(
        set(entries)
        == {
            body,
            seal,
        },
        "STARTUP_CATCHUP_EXTRA_EVIDENCE",
    )

    return body, seal


def certify_capture(
    *,
    base_path,
    base_sha256,
    source_path,
    capture_directory,
    request,
    output_path,
):
    require(
        type(request) is dict
        and request.get("schema")
        == REQUEST_SCHEMA
        and request.get(
            "runtime_admission"
        ) is False
        and request.get(
            "execution_authority"
        ) is False,
        "STARTUP_CATCHUP_REQUEST_SCHEMA",
    )

    base_raw = bounded_read(
        Path(
            base_path
        ).resolve()
    )

    require(
        sha256(
            base_raw
        ).hexdigest()
        == base_sha256,
        "STARTUP_CATCHUP_BASE_PIN",
    )

    base = certify_bootstrap(
        base_raw,
        expected_sha256=
            base_sha256,
    )

    require(
        base.source
        in ALLOWED_BASE_SOURCES,
        "STARTUP_CATCHUP_BASE_SOURCE",
    )

    body_path, seal_path = (
        _capture_files(
            capture_directory
        )
    )

    body_raw = bounded_read(
        body_path
    )

    seal_raw = bounded_read(
        seal_path
    )

    lines = (
        body_raw.splitlines()
    )

    require(
        bool(lines),
        "STARTUP_CATCHUP_EMPTY_BODY",
    )

    header = parse(
        lines[0]
    )

    require(
        header.get("schema")
        == "arms.nt.chart-catchup.header.v1"
        and header.get("provider")
        == request[
            "expected_provider_enum"
        ],
        "STARTUP_CATCHUP_HEADER_IDENTITY",
    )

    require(
        _parse_label(
            header[
                "requested_from_close"
            ]
        )
        == _parse_label(
            request[
                "from_close_utc"
            ]
        ),
        "STARTUP_CATCHUP_FROM_MISMATCH",
    )

    request_selection = request.get(
        "through_selection"
    )

    require(
        request_selection
        in {
            "HOST_UTC_OPERATIONAL_HINT_CLIPPED_TO_REVIEWED_SESSION",
            "CHART_LATEST_CLOSED",
        },
        "STARTUP_CATCHUP_THROUGH_SELECTION",
    )

    if (
        request_selection
        == "CHART_LATEST_CLOSED"
    ):
        require(
            request.get(
                "through_close_utc"
            )
            == "LATEST_CLOSED"
            and header.get(
                "configured_through_close"
            )
            == "LATEST_CLOSED"
            and header.get(
                "through_selection"
            )
            == "CHART_LATEST_CLOSED",
            "STARTUP_CATCHUP_THROUGH_MODE_MISMATCH",
        )

    else:
        require(
            header.get(
                "through_selection"
            )
            == "EXPLICIT_UTC"
            and _parse_label(
                header[
                    "configured_through_close"
                ]
            )
            == _parse_label(
                request[
                    "through_close_utc"
                ]
            )
            and _parse_label(
                header[
                    "requested_through_close"
                ]
            )
            == _parse_label(
                request[
                    "through_close_utc"
                ]
            ),
            "STARTUP_CATCHUP_THROUGH_MISMATCH",
        )

    source_raw = bounded_read(
        Path(
            source_path
        ).resolve()
    )

    verify_chart_catchup_source(
        source_raw,
        mismatch_reason=(
            "STARTUP_CATCHUP_INSTALLED_SOURCE"
        ),
    )

    composite_raw, report = (
        build_bundle(
            base_raw,
            body_raw,
            seal_raw,
            source_raw,
        )
    )

    digest = sha256(
        composite_raw
    ).hexdigest()

    composite = certify_bootstrap(
        composite_raw,
        expected_sha256=digest,
    )

    require(
        composite.source
        == MERGED_SOURCE,
        "STARTUP_CATCHUP_COMPOSITE_SOURCE",
    )

    output = local_path(
        Path(
            output_path
        ).resolve()
    )

    require(
        output.parent.is_dir()
        and not output.exists(),
        "STARTUP_CATCHUP_OUTPUT_PATH",
    )

    with output.open(
        "xb"
    ) as handle:
        handle.write(
            composite_raw
        )

    return {
        "bootstrap":
            composite,
        "sha256":
            digest,
        "bars":
            len(
                composite.bars
            ),
        "cutoff":
            composite.bars[-1].label,
        "source":
            composite.source,
        "report":
            report,
        "output":
            str(output),
        "runtime_admission":
            False,
        "execution_authority":
            False,
    }
