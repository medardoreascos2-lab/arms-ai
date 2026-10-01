"""Dynamic latest-closed startup contract; no NinjaTrader process and no orders."""
from datetime import (
    datetime,
    timezone,
)
from hashlib import sha256
import json
from pathlib import Path

import pytest

from backend.market_data.certified_bootstrap_v1 import (
    certify_bootstrap,
)
from backend.tests.test_chart_catchup_bridge_v1 import (
    bridge_evidence,
    successful_labels,
    base_raw,
)
from tools.startup_chart_catchup_v1 import (
    certify_capture,
    prepare_request,
)


SOURCE = Path(
    "integrations/ninjatrader/"
    "ArmsChartCatchupBridgeV1.cs"
).resolve()


def base_fixture(
    tmp_path,
):
    raw = base_raw()

    digest = sha256(
        raw
    ).hexdigest()

    path = (
        tmp_path
        / "base.bundle.json"
    )

    path.write_bytes(
        raw
    )

    bootstrap = certify_bootstrap(
        raw,
        expected_sha256=digest,
    )

    return (
        path,
        digest,
        bootstrap,
    )


def write_capture(
    capture,
    body,
    seal,
):
    header = json.loads(
        body.splitlines()[0]
    )

    run_id = header[
        "run_id"
    ]

    body_path = (
        capture
        / (
            run_id
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


def test_prepare_request_dynamic_mode_uses_latest_closed_sentinel(
    tmp_path,
):
    _, _, bootstrap = (
        base_fixture(
            tmp_path
        )
    )

    run = (
        tmp_path
        / "run"
    )

    run.mkdir()

    request = prepare_request(
        run,
        bootstrap,
        now_utc=datetime(
            2026,
            9,
            21,
            22,
            2,
            30,
            tzinfo=timezone.utc,
        ),
        latest_closed=True,
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
        == "LATEST_CLOSED"
    )

    assert (
        request[
            "through_selection"
        ]
        == "CHART_LATEST_CLOSED"
    )

    assert (
        request[
            "absolute_time_authority"
        ]
        == "NONE"
    )

    assert (
        request[
            "runtime_admission"
        ]
        is False
    )

    assert (
        request[
            "execution_authority"
        ]
        is False
    )


def test_dynamic_request_accepts_only_latest_closed_product_proof(
    tmp_path,
):
    base_path, digest, bootstrap = (
        base_fixture(
            tmp_path
        )
    )

    run = (
        tmp_path
        / "run"
    )

    run.mkdir()

    request = prepare_request(
        run,
        bootstrap,
        now_utc=datetime(
            2026,
            9,
            21,
            22,
            2,
            30,
            tzinfo=timezone.utc,
        ),
        latest_closed=True,
    )

    body, seal = bridge_evidence(
        successful_labels(),
        latest_closed=True,
    )

    capture = Path(
        request[
            "output_directory"
        ]
    )

    write_capture(
        capture,
        body,
        seal,
    )

    result = certify_capture(
        base_path=base_path,
        base_sha256=digest,
        source_path=SOURCE,
        capture_directory=capture,
        request=request,
        output_path=
            run
            / "certified.bundle.json",
    )

    assert (
        result[
            "cutoff"
        ]
        == "2026-09-21T22:02:00.0000000Z"
    )

    assert (
        result[
            "bars"
        ]
        == 5
    )

    assert (
        result[
            "runtime_admission"
        ]
        is False
    )

    assert (
        result[
            "execution_authority"
        ]
        is False
    )


def test_dynamic_request_rejects_explicit_product_capture(
    tmp_path,
):
    base_path, digest, bootstrap = (
        base_fixture(
            tmp_path
        )
    )

    run = (
        tmp_path
        / "run"
    )

    run.mkdir()

    request = prepare_request(
        run,
        bootstrap,
        now_utc=datetime(
            2026,
            9,
            21,
            22,
            2,
            30,
            tzinfo=timezone.utc,
        ),
        latest_closed=True,
    )

    body, seal = bridge_evidence(
        successful_labels(),
        latest_closed=False,
    )

    capture = Path(
        request[
            "output_directory"
        ]
    )

    write_capture(
        capture,
        body,
        seal,
    )

    with pytest.raises(
        ValueError,
        match=
            "STARTUP_CATCHUP_THROUGH_MODE_MISMATCH",
    ):
        certify_capture(
            base_path=base_path,
            base_sha256=digest,
            source_path=SOURCE,
            capture_directory=capture,
            request=request,
            output_path=
                run
                / "certified.bundle.json",
        )


def test_startup_code_selects_dynamic_mode_and_no_execution_surface():
    text = Path(
        "tools/"
        "analysis_native_startup_v1.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "latest_closed=True"
        in text
    )

    for forbidden in (
        "SubmitOrder",
        "CreateOrder(",
        "ChangeOrder",
        "CancelOrder",
        "Account.All",
        "AtmStrategy",
        "EnterLong",
        "EnterShort",
    ):
        assert forbidden not in text
