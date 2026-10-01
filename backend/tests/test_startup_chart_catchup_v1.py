"""Startup chart catch-up coordinator tests; no NinjaTrader process or orders."""
from copy import deepcopy
from datetime import (
    datetime,
    timezone,
)
from hashlib import sha256
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
    successful_labels,
)
from tools.startup_chart_catchup_v1 import (
    await_capture,
    capture_status,
    certify_capture,
    latest_expected_close,
    next_expected_close,
    prepare_request,
)


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
):
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

    return body_path, seal_path


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

    assert (
        capture_status(
            capture
        )
        == "READY"
    )


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
