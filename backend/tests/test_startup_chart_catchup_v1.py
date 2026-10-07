"""Startup chart catch-up coordinator tests; no NinjaTrader process or orders."""
from copy import deepcopy
from dataclasses import replace
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
    MERGED_SOURCE,
)
from backend.tests.test_chart_catchup_bridge_v1 import (
    SOURCE,
    base_raw,
    bridge_evidence,
    october_composite,
    successful_labels,
)
from tools.startup_chart_catchup_v1 import (
    await_capture,
    capture_status,
    certify_capture,
    latest_expected_close,
    MAX_CATCHUP_DURATION,
    next_expected_close,
    prepare_request,
)


def _request_at_duration(tmp_path, monkeypatch, duration):
    _, data = native()
    run = tmp_path / ("range-" + str(int(duration.total_seconds())))
    run.mkdir()
    start = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "tools.startup_chart_catchup_v1.next_expected_close",
        lambda _bootstrap: start)
    monkeypatch.setattr(
        "tools.startup_chart_catchup_v1.latest_expected_close",
        lambda _bootstrap, _now: start + duration)
    return prepare_request(run, data, now_utc=start + duration)


@pytest.mark.parametrize("duration", (
    timedelta(minutes=1), MAX_CATCHUP_DURATION,
))
def test_bounded_range_at_or_below_limit_passes(
        tmp_path, monkeypatch, duration):
    request = _request_at_duration(tmp_path, monkeypatch, duration)
    assert request["range_contract"] == "EXACT_CONTIGUOUS_NO_TRUNCATION"
    assert request["range_duration_seconds"] == int(duration.total_seconds())
    assert request["range_maximum_seconds"] == 2 * 24 * 60 * 60


def test_range_above_limit_blocks_without_clipping(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="STARTUP_CATCHUP_RANGE_LIMIT"):
        _request_at_duration(
            tmp_path, monkeypatch, MAX_CATCHUP_DURATION + timedelta(minutes=1))


def test_future_base_timestamp_blocks(tmp_path, monkeypatch):
    _, data = native()
    run = tmp_path / "future-base"
    run.mkdir()
    now = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "tools.startup_chart_catchup_v1.next_expected_close",
        lambda _bootstrap: now + timedelta(minutes=1))
    monkeypatch.setattr(
        "tools.startup_chart_catchup_v1.latest_expected_close",
        lambda _bootstrap, _now: now)
    with pytest.raises(ValueError, match="STARTUP_CATCHUP_BASE_NOT_BEHIND"):
        prepare_request(run, data, now_utc=now)


def test_invalid_naive_timestamp_blocks(tmp_path):
    _, data = native()
    run = tmp_path / "naive-now"
    run.mkdir()
    with pytest.raises(ValueError, match="STARTUP_CATCHUP_UTC_REQUIRED"):
        prepare_request(run, data, now_utc=datetime(2026, 10, 1))


def test_fresh_current_request_has_no_historical_bootstrap(tmp_path):
    _, data = native()
    run = tmp_path / "no-historical-bootstrap"
    run.mkdir()
    request = prepare_request(
        run, data,
        now_utc=datetime(2026, 9, 21, 22, 2, tzinfo=timezone.utc),
        latest_closed=True)
    serialized = json.dumps(request, sort_keys=True)
    assert "HistoricalBootstrap" not in serialized
    assert request["range_contract"] == "EXACT_CONTIGUOUS_NO_TRUNCATION"


def native():
    raw = base_raw()

    data = certify_bootstrap(
        raw,
        expected_sha256=
            sha256(raw).hexdigest(),
    )

    return raw, data


def prepared(tmp_path):
    raw, data = native()

    run = (
        tmp_path
        / "runtime"
    )

    run.mkdir()

    request = prepare_request(
        run,
        data,
        now_utc=datetime(
            2026,
            9,
            21,
            22,
            2,
            30,
            tzinfo=timezone.utc,
        ),
    )

    capture = (
        run
        / "chart-catchup"
    )

    return (
        raw,
        data,
        run,
        capture,
        request,
    )


def write_capture(
    capture,
    labels=None,
    *,
    lifecycle=True,
):
    body, seal = bridge_evidence(
        successful_labels()
        if labels is None
        else labels
    )

    session = str(
        uuid4()
    )

    body_path = (
        capture
        / (
            session
            + ".chart-catchup.jsonl"
        )
    )

    seal_path = Path(
        str(body_path)
        + ".done.json"
    )

    body_path.write_bytes(
        body
    )

    seal_path.write_bytes(
        seal
    )

    if lifecycle:
        write_lifecycle(
            capture,
            EXPLICIT_LIFECYCLE,
        )

    return body_path, seal_path


EXPLICIT_LIFECYCLE = (
    "WAITING_FOR_LIVE_HELLO",
    "CAPTURE_STARTED",
    "CAPTURE_BODY_WRITTEN",
    "CAPTURE_SEAL_WRITTEN",
    "CAPTURE_COMPLETE",
)


SUCCESSFUL_LIFECYCLE = (
    "WAITING_FOR_LIVE_HELLO",
    "LIVE_HELLO_ACCEPTED",
    "ALIGNMENT_BAR_CAPTURED",
    "WAITING_FOR_SECOND_BAR_ADVANCE",
    "CAPTURE_STARTED",
    "CAPTURE_BODY_WRITTEN",
    "CAPTURE_SEAL_WRITTEN",
    "CAPTURE_COMPLETE",
)


def lifecycle_bytes(states=SUCCESSFUL_LIFECYCLE):
    return b"".join(
        json.dumps(
            {
                "schema": "arms.nt.chart-catchup.lifecycle.v1",
                "sequence": sequence,
                "event_time": f"2026-09-21T22:02:{sequence:02d}.0000000Z",
                "state": state,
                "reason": None,
                "observation_only": True,
                "runtime_admission": False,
                "execution_authority": False,
            },
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
        for sequence, state in enumerate(states)
    )


def write_lifecycle(capture, states=SUCCESSFUL_LIFECYCLE):
    (capture / "catchup-lifecycle.jsonl").write_bytes(
        lifecycle_bytes(states)
    )


def test_request_derives_reviewed_session_boundaries(
    tmp_path,
):
    _, data = native()

    assert (
        next_expected_close(
            data
        ).isoformat()
        == "2026-09-21T21:00:00+00:00"
    )

    assert (
        latest_expected_close(
            data,
            datetime(
                2026,
                9,
                21,
                22,
                2,
                30,
                tzinfo=timezone.utc,
            ),
        ).isoformat()
        == "2026-09-21T22:02:00+00:00"
    )

    run = tmp_path / "run"
    run.mkdir()

    request = prepare_request(
        run,
        data,
        now_utc=datetime(
            2026,
            9,
            21,
            22,
            2,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert (
        request[
            "from_close_utc"
        ]
        == "2026-09-21T21:00:00Z"
    )

    assert (
        request[
            "through_close_utc"
        ]
        == "2026-09-21T22:02:00Z"
    )

    assert (
        request[
            "runtime_admission"
        ]
        is False
    )

    assert not any(
        (
            run
            / "chart-catchup"
        ).iterdir()
    )


def test_exact_capture_certifies_composite(
    tmp_path,
):
    (
        base,
        _,
        run,
        capture,
        request,
    ) = prepared(
        tmp_path
    )

    write_capture(
        capture
    )

    source = (
        tmp_path
        / "ArmsChartCatchupBridgeV1.cs"
    )

    source.write_bytes(
        SOURCE
    )

    base_path = (
        tmp_path
        / "base.json"
    )

    base_path.write_bytes(
        base
    )

    output = (
        run
        / "certified-chart-catchup.bundle.json"
    )

    result = certify_capture(
        base_path=
            base_path,
        base_sha256=
            sha256(base).hexdigest(),
        source_path=
            source,
        capture_directory=
            capture,
        request=request,
        output_path=output,
    )

    assert (
        result["source"]
        == MERGED_SOURCE
    )

    assert (
        result["bars"]
        == 5
    )

    assert (
        result["cutoff"]
        == "2026-09-21T22:02:00.0000000Z"
    )

    assert (
        result[
            "runtime_admission"
        ]
        is False
    )

    assert (
        output.read_bytes()
        and sha256(
            output.read_bytes()
        ).hexdigest()
        == result["sha256"]
    )


def test_merged_base_derives_exact_incremental_close_and_certifies_again(
    tmp_path,
):
    base, data = october_composite()
    run = tmp_path / "runtime"
    run.mkdir()
    request = prepare_request(
        run,
        data,
        now_utc=datetime(
            2026, 10, 1, 20, 51,
            tzinfo=timezone.utc,
        ),
    )
    assert request["from_close_utc"] == "2026-10-01T20:50:00Z"
    assert request["through_close_utc"] == "2026-10-01T20:51:00Z"
    assert request["runtime_admission"] is False
    assert request["execution_authority"] is False

    labels = [
        datetime(2026, 10, 1, 20, minute, tzinfo=timezone.utc)
        for minute in (50, 51)
    ]
    capture = run / "chart-catchup"
    write_capture(capture, labels)
    source = tmp_path / "ArmsChartCatchupBridgeV1.cs"
    source.write_bytes(SOURCE)
    base_path = tmp_path / "first-composite.json"
    base_path.write_bytes(base)
    output = run / "certified-chart-catchup.bundle.json"

    result = certify_capture(
        base_path=base_path,
        base_sha256=sha256(base).hexdigest(),
        source_path=source,
        capture_directory=capture,
        request=request,
        output_path=output,
    )

    assert result["source"] == MERGED_SOURCE
    assert result["bars"] == len(data.bars) + 2
    assert result["runtime_admission"] is False
    assert result["execution_authority"] is False
    chained = certify_bootstrap(
        output.read_bytes(),
        expected_sha256=result["sha256"],
    )
    assert chained.bars[:len(data.bars)] == data.bars
    assert len({bar.label for bar in chained.bars}) == len(chained.bars)


@pytest.mark.parametrize(
    "source",
    (
        "UNKNOWN",
        "LIVE_TAIL",
        "UNTRUSTED_HISTORY",
        "NATIVE_HISTORICAL_REPOSITORY+FAKE",
    ),
)
def test_next_expected_close_rejects_every_unrecognized_source(source):
    _, data = october_composite()
    with pytest.raises(
        ValueError,
        match="STARTUP_CATCHUP_NATIVE_BASE_REQUIRED",
    ):
        next_expected_close(
            replace(data, source=source)
        )


@pytest.mark.parametrize(
    "fault",
    (
        "request_from",
        "request_through",
        "extra_file",
        "source",
        "base_pin",
    ),
)
def test_certification_faults_fail_closed(
    tmp_path,
    fault,
):
    (
        base,
        _,
        run,
        capture,
        request,
    ) = prepared(
        tmp_path
    )

    write_capture(
        capture
    )

    request = deepcopy(
        request
    )

    if fault == "request_from":
        request[
            "from_close_utc"
        ] = (
            "2026-09-21T22:01:00Z"
        )

    elif fault == "request_through":
        request[
            "through_close_utc"
        ] = (
            "2026-09-21T22:01:00Z"
        )

    elif fault == "extra_file":
        (
            capture
            / "unexpected.txt"
        ).write_text(
            "unexpected",
            encoding="utf-8",
        )

    source = (
        tmp_path
        / "ArmsChartCatchupBridgeV1.cs"
    )

    source.write_bytes(
        b"wrong"
        if fault == "source"
        else SOURCE
    )

    base_path = (
        tmp_path
        / "base.json"
    )

    base_path.write_bytes(
        base
    )

    digest = (
        "0" * 64
        if fault == "base_pin"
        else sha256(
            base
        ).hexdigest()
    )

    with pytest.raises(
        ValueError,
    ):
        certify_capture(
            base_path=
                base_path,
            base_sha256=
                digest,
            source_path=
                source,
            capture_directory=
                capture,
            request=request,
            output_path=
                run
                / "certified.bundle.json",
        )


def test_request_directory_must_be_fresh(
    tmp_path,
):
    _, data = native()

    run = tmp_path / "run"
    run.mkdir()

    prepare_request(
        run,
        data,
        now_utc=datetime(
            2026,
            9,
            21,
            22,
            2,
            tzinfo=timezone.utc,
        ),
    )

    with pytest.raises(
        ValueError,
    ):
        prepare_request(
            run,
            data,
            now_utc=datetime(
                2026,
                9,
                21,
                22,
                2,
                tzinfo=timezone.utc,
            ),
        )



def test_capture_status_accepts_only_productive_writer_lifecycle(
    tmp_path,
):
    capture = (
        tmp_path
        / "capture"
    )

    capture.mkdir()

    assert (
        capture_status(
            capture
        )
        == "WAITING"
    )

    session = str(
        uuid4()
    )

    body = (
        capture
        / (
            session
            + ".chart-catchup.jsonl"
        )
    )

    temporary = Path(
        str(body)
        + ".done.tmp"
    )

    seal = Path(
        str(body)
        + ".done.json"
    )

    body.write_bytes(
        b"body\n"
    )

    assert (
        capture_status(
            capture
        )
        == "BODY_WRITTEN"
    )

    temporary.write_bytes(
        b"seal"
    )

    assert (
        capture_status(
            capture
        )
        == "SEALING"
    )

    temporary.replace(
        seal
    )

    write_lifecycle(capture)

    assert (
        capture_status(
            capture
        )
        == "READY"
    )


def test_body_and_seal_without_lifecycle_are_rejected(tmp_path):
    capture = tmp_path / "capture"
    capture.mkdir()
    write_capture(capture, lifecycle=False)

    with pytest.raises(
        ValueError,
        match="STARTUP_CATCHUP_LIFECYCLE_INCOMPLETE",
    ):
        capture_status(capture)


@pytest.mark.parametrize(
    "diagnostic",
    (
        b"",
        lifecycle_bytes()[:20],
        lifecycle_bytes(SUCCESSFUL_LIFECYCLE[:-1]),
    ),
)
def test_body_and_seal_without_complete_lifecycle_record_are_rejected(
    tmp_path,
    diagnostic,
):
    capture = tmp_path / "capture"
    capture.mkdir()
    write_capture(capture, lifecycle=False)
    (capture / "catchup-lifecycle.jsonl").write_bytes(diagnostic)

    with pytest.raises(
        ValueError,
        match="STARTUP_CATCHUP_LIFECYCLE_INCOMPLETE",
    ):
        capture_status(capture)


@pytest.mark.parametrize(
    "fault",
    (
        "unexpected",
        "seal_without_body",
        "duplicate_body",
        "temporary_without_body",
    ),
)
def test_capture_status_faults_fail_closed(
    tmp_path,
    fault,
):
    capture = (
        tmp_path
        / "capture"
    )

    capture.mkdir()

    session = str(
        uuid4()
    )

    body = (
        capture
        / (
            session
            + ".chart-catchup.jsonl"
        )
    )

    if fault == "unexpected":
        (
            capture
            / "unexpected.txt"
        ).write_text(
            "x",
            encoding="utf-8",
        )

    elif fault == "seal_without_body":
        Path(
            str(body)
            + ".done.json"
        ).write_text(
            "{}",
            encoding="utf-8",
        )

    elif fault == "temporary_without_body":
        Path(
            str(body)
            + ".done.tmp"
        ).write_text(
            "{}",
            encoding="utf-8",
        )

    else:
        body.write_text(
            "a",
            encoding="utf-8",
        )

        other = (
            capture
            / (
                str(uuid4())
                + ".chart-catchup.jsonl"
            )
        )

        other.write_text(
            "b",
            encoding="utf-8",
        )

    with pytest.raises(
        ValueError,
    ):
        capture_status(
            capture
        )


def test_await_capture_checks_guard_and_returns_only_ready(
    tmp_path,
):
    capture = (
        tmp_path
        / "capture"
    )

    capture.mkdir()

    body, seal = bridge_evidence(
        successful_labels()
    )

    session = str(
        uuid4()
    )

    body_path = (
        capture
        / (
            session
            + ".chart-catchup.jsonl"
        )
    )

    seal_path = Path(
        str(body_path)
        + ".done.json"
    )

    body_path.write_bytes(
        body
    )

    seal_path.write_bytes(
        seal
    )

    write_lifecycle(capture)

    calls = []

    result = await_capture(
        capture,
        timeout_seconds=5,
        guard=lambda:
            calls.append(
                "guard"
            ),
        monotonic=lambda: 0,
        sleeper=lambda _: None,
    )

    assert result == "READY"

    assert calls == [
        "guard"
    ]


def test_await_capture_timeout_fails_closed(
    tmp_path,
):
    capture = (
        tmp_path
        / "capture"
    )

    capture.mkdir()

    clock = [
        0.0
    ]

    guards = []

    def monotonic():
        return clock[0]

    def sleeper(seconds):
        clock[0] += seconds

    with pytest.raises(
        ValueError,
        match="STARTUP_CATCHUP_CAPTURE_TIMEOUT",
    ):
        await_capture(
            capture,
            timeout_seconds=.5,
            guard=lambda:
                guards.append(
                    clock[0]
                ),
            poll_seconds=.25,
            monotonic=monotonic,
            sleeper=sleeper,
        )

    assert len(guards) >= 2
