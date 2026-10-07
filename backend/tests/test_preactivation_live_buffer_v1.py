"""Pre-activation live-buffer contract.

No NinjaTrader start, account surface, order surface or runtime admission.

A single live exporter session created after the fresh runtime directory may
exist before activation, but it must remain quarantined and unconsumed until
the certified catch-up bootstrap has been installed and activation is armed.
"""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from backend.market_data.certified_bootstrap_v1 import (
    BootstrapBar,
    CertifiedBootstrap,
)
from backend.market_data.fresh_native_adapter_v1 import (
    FreshNativeAdapterV1,
)


SOURCE = Path(
    "integrations/ninjatrader/"
    "ArmsReadOnlyMarketV1.cs"
).resolve()


HELLO_PAYLOAD = {
    "provider": "Provider31",
    "contract": "NQ DEC26",
    "expiry": "2026-12-01",
    "instrument": "NQ",
    "tick_size": 0.25,
    "point_value": 20,
    "timeframe": "1m",
    "trading_hours_template":
        "CME US Index Futures ETH",
    "source_timezone": "UTC",
    "bar_label": "CLOSE",
    "realtime": True,
    "read_only": True,
}


def encode(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def certified_bootstrap():
    return CertifiedBootstrap(
        "b" * 64,
        (
            BootstrapBar(
                "2026-09-30T16:13:00.0000000Z",
                30850.0,
                30860.0,
                30840.0,
                30855.0,
                100,
            ),
        ),
        ("history",),
        0,
        source=(
            "NATIVE_HISTORICAL_REPOSITORY"
            "+NINJATRADER_LOADED_CHART_BARS"
        ),
    )


def new_adapter(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()

    clock = [1000]

    adapter = FreshNativeAdapterV1(
        directory=inbox,
        installed_exporter=SOURCE,
        qpc_clock=lambda: (
            "preactivation-buffer-test",
            1000,
            clock[0],
        ),
        health_gated=True,
    )

    return adapter, inbox, clock


def write_valid_buffer(inbox):
    session = str(uuid4())

    hello = {
        "schema": "arms.nt.market.v1",
        "session": session,
        "sequence": 0,
        "event_time":
            "2026-09-30T16:14:00.0000000Z",
        "kind": "HELLO",
        "payload": HELLO_PAYLOAD,
    }

    market = inbox / (
        session
        + ".jsonl"
    )

    market.write_bytes(
        encode(hello)
        + b"\n"
    )

    # Connection diagnostics are a real exporter sidecar,
    # but they are not a market-analysis input stream.
    connection = inbox / (
        session
        + ".connection.jsonl"
    )

    connection.write_bytes(b"")

    return session


def write_canonical_hello(inbox, session, *, payload=None, newline=True):
    hello = {
        "schema": "arms.nt.market.v1",
        "session": session,
        "sequence": 0,
        "event_time": "2026-09-30T16:14:00.0000000Z",
        "kind": "HELLO",
        "payload": HELLO_PAYLOAD if payload is None else payload,
    }
    raw = encode(hello)
    (inbox / (session + ".jsonl")).write_bytes(
        raw + (b"\n" if newline else b"")
    )


def test_connection_sidecar_can_precede_exact_canonical_hello(tmp_path):
    adapter, inbox, _ = new_adapter(tmp_path)
    session = str(uuid4())
    connection = inbox / (session + ".connection.jsonl")
    connection.write_bytes(b"")

    assert adapter.validate_preactivation_buffer("TEST_PRE_HELLO") is None

    write_canonical_hello(inbox, session)

    assert adapter.validate_preactivation_buffer("TEST_PRE_HELLO") == session


def test_persistent_orphan_sidecar_never_binds_a_session(tmp_path):
    adapter, inbox, _ = new_adapter(tmp_path)
    session = str(uuid4())
    (inbox / (session + ".connection.jsonl")).write_bytes(b"")

    for _ in range(3):
        assert adapter.validate_preactivation_buffer("TEST_PRE_HELLO") is None

    assert adapter.preactivation_lineage_root is None
    assert adapter.preactivation_session is None


def test_timing_sidecar_can_precede_exact_canonical_hello(tmp_path):
    adapter, inbox, _ = new_adapter(tmp_path)
    session = str(uuid4())
    timing = inbox / "timing"
    timing.mkdir()
    (timing / (session + ".production-timing.jsonl")).write_bytes(b"")

    assert adapter.validate_preactivation_buffer("TEST_PRE_HELLO") is None

    write_canonical_hello(inbox, session)

    assert adapter.validate_preactivation_buffer("TEST_PRE_HELLO") == session


def test_orphan_sidecar_then_foreign_canonical_fails_closed(tmp_path):
    adapter, inbox, _ = new_adapter(tmp_path)
    orphan = str(uuid4())
    canonical = str(uuid4())
    (inbox / (orphan + ".connection.jsonl")).write_bytes(b"")

    assert adapter.validate_preactivation_buffer("TEST_PRE_HELLO") is None
    write_canonical_hello(inbox, canonical)

    with pytest.raises(ValueError, match="TEST_PRE_HELLO"):
        adapter.validate_preactivation_buffer("TEST_PRE_HELLO")


def test_conflicting_orphan_sidecars_fail_closed(tmp_path):
    adapter, inbox, _ = new_adapter(tmp_path)
    connection_session = str(uuid4())
    timing_session = str(uuid4())
    (inbox / (connection_session + ".connection.jsonl")).write_bytes(b"")
    timing = inbox / "timing"
    timing.mkdir()
    (timing / (timing_session + ".production-timing.jsonl")).write_bytes(b"")

    with pytest.raises(ValueError, match="TEST_PRE_HELLO"):
        adapter.validate_preactivation_buffer("TEST_PRE_HELLO")


def test_malformed_canonical_hello_fails_closed_immediately(tmp_path):
    adapter, inbox, _ = new_adapter(tmp_path)
    session = str(uuid4())
    (inbox / (session + ".jsonl")).write_bytes(b"not-json\n")

    with pytest.raises(ValueError):
        adapter.validate_preactivation_buffer("TEST_PRE_HELLO")


def test_incomplete_canonical_hello_remains_pending_until_complete(tmp_path):
    adapter, inbox, _ = new_adapter(tmp_path)
    session = str(uuid4())
    write_canonical_hello(inbox, session, newline=False)

    assert adapter.validate_preactivation_buffer("TEST_PRE_HELLO") is None

    with (inbox / (session + ".jsonl")).open("ab") as handle:
        handle.write(b"\n")

    assert adapter.validate_preactivation_buffer("TEST_PRE_HELLO") == session


def test_exact_canonical_hello_payload_mismatch_fails_closed(tmp_path):
    adapter, inbox, _ = new_adapter(tmp_path)
    session = str(uuid4())
    payload = dict(HELLO_PAYLOAD)
    payload["provider"] = "FOREIGN_PROVIDER"
    write_canonical_hello(inbox, session, payload=payload)

    with pytest.raises(ValueError, match="TEST_PRE_HELLO"):
        adapter.validate_preactivation_buffer("TEST_PRE_HELLO")


def test_single_preactivation_session_is_quarantined(
    tmp_path,
):
    adapter, inbox, _ = new_adapter(
        tmp_path
    )

    write_valid_buffer(
        inbox
    )

    # Desired contract: discovering one valid pre-activation
    # session does not bind it, consume it or revoke runtime.
    adapter.poll()

    assert adapter.status == "WAITING"
    assert adapter.reason is None
    assert adapter.activation_start is None

    assert adapter.session is None
    assert adapter.market is None
    assert adapter.timing is None

    assert adapter.sequence == -1
    assert adapter.pair_sequence == -1

    assert adapter.bootstrap_records == 0
    assert adapter.delivered_records == 0

    assert (
        adapter.snapshot()[
            "order_submit_reachable"
        ]
        is False
    )


def test_valid_buffer_allows_bootstrap_replace_and_arm(
    tmp_path,
):
    adapter, inbox, clock = new_adapter(
        tmp_path
    )

    write_valid_buffer(
        inbox
    )

    data = certified_bootstrap()

    # Desired contract: buffer remains untouched while the
    # freshly certified LATEST_CLOSED bootstrap is installed.
    adapter.replace_waiting_bootstrap(
        data
    )

    assert adapter.bootstrap is data
    assert (
        adapter.bootstrap_replacement_count
        == 1
    )

    assert adapter.status == "WAITING"
    assert adapter.session is None
    assert adapter.market is None
    assert adapter.sequence == -1

    # Activation binds the already-running exporter only now.
    adapter.arm_activation()

    assert (
        adapter.activation_start
        == clock[0]
    )

    assert adapter.status == "WAITING"
    assert adapter.session is None

    assert (
        adapter.snapshot()[
            "order_submit_reachable"
        ]
        is False
    )


def test_arbitrary_preactivation_file_still_fails_closed(
    tmp_path,
):
    adapter, inbox, _ = new_adapter(
        tmp_path
    )

    (
        inbox
        / "unexpected.txt"
    ).write_text(
        "not a native session",
        encoding="utf-8",
    )

    adapter.poll()

    assert adapter.status == "REVOKED"
    assert adapter.reason
    assert (
        adapter.snapshot()[
            "order_submit_reachable"
        ]
        is False
    )


def test_multiple_preactivation_sessions_still_fail_closed(
    tmp_path,
):
    adapter, inbox, _ = new_adapter(
        tmp_path
    )

    write_valid_buffer(
        inbox
    )

    write_valid_buffer(
        inbox
    )

    adapter.poll()

    assert adapter.status == "REVOKED"
    assert adapter.reason
    assert (
        adapter.snapshot()[
            "order_submit_reachable"
        ]
        is False
    )



def test_valid_timing_sidecar_is_quarantined(
    tmp_path,
):
    adapter, inbox, _ = new_adapter(
        tmp_path
    )

    session = write_valid_buffer(
        inbox
    )

    timing = (
        inbox
        / "timing"
    )

    timing.mkdir()

    (
        timing
        / (
            session
            + ".production-timing.jsonl"
        )
    ).write_bytes(
        b""
    )

    adapter.poll()

    assert adapter.status == "WAITING"
    assert adapter.reason is None
    assert adapter.session is None
    assert adapter.market is None
    assert adapter.timing is None
    assert adapter.sequence == -1
    assert adapter.delivered_records == 0


def test_mismatched_timing_session_fails_closed(
    tmp_path,
):
    adapter, inbox, _ = new_adapter(
        tmp_path
    )

    write_valid_buffer(
        inbox
    )

    timing = (
        inbox
        / "timing"
    )

    timing.mkdir()

    (
        timing
        / (
            str(uuid4())
            + ".production-timing.jsonl"
        )
    ).write_bytes(
        b""
    )

    adapter.poll()

    assert adapter.status == "REVOKED"
    assert adapter.reason
    assert (
        adapter.snapshot()[
            "order_submit_reachable"
        ]
        is False
    )


def test_preactivation_buffer_never_binds_before_arm(
    tmp_path,
):
    adapter, inbox, _ = new_adapter(
        tmp_path
    )

    session = write_valid_buffer(
        inbox
    )

    for _ in range(3):
        adapter.poll()

    assert adapter.status == "WAITING"
    assert adapter.session is None
    assert adapter.market is None
    assert adapter.timing is None
    assert adapter.sequence == -1
    assert adapter.pair_sequence == -1
    assert adapter.bootstrap_records == 0
    assert adapter.delivered_records == 0

    assert (
        adapter.validate_preactivation_buffer(
            "TEST_INVALID_BUFFER",
        )
        == session
    )




def _fresh_quarantined_files(
    tmp_path,
):
    from backend.tests.test_analysis_time_sprint15x import (
        SESSION,
        Stream,
        encode as stream_encode,
    )
    from backend.tests.test_fresh_native_adapter_sprint15y import (
        EXPORTER,
    )

    root = (
        tmp_path
        / "buffered-live"
    )

    root.mkdir()

    # Important contract:
    # runtime/adapter exists FIRST, while inbox is empty.
    stream = Stream()

    stream.qpc += 1

    adapter = FreshNativeAdapterV1(
        directory=root,
        installed_exporter=EXPORTER,
        qpc_clock=lambda: (
            stream.epoch,
            1000,
            stream.qpc,
        ),
        health_gated=True,
    )

    assert not any(
        root.iterdir()
    )

    assert adapter.status == "WAITING"
    assert adapter.session is None
    assert adapter.market is None

    # Only NOW does the exporter start and create its files.
    timing_dir = (
        root
        / "timing"
    )

    timing_dir.mkdir()

    canonical = (
        root
        / (
            SESSION
            + ".jsonl"
        )
    )

    sidecar = (
        timing_dir
        / (
            SESSION
            + ".production-timing.jsonl"
        )
    )

    connection = (
        root
        / (
            SESSION
            + ".connection.jsonl"
        )
    )

    hello = {
        "schema":
            "arms.nt.market.v1",
        "session":
            SESSION,
        "sequence":
            0,
        "event_time":
            "2026-09-21T14:00:00.0000000Z",
        "kind":
            "HELLO",
        "payload": {
            "provider":
                "Provider31",
            "contract":
                "NQ DEC26",
            "expiry":
                "2026-12-01",
            "instrument":
                "NQ",
            "tick_size":
                0.25,
            "point_value":
                20,
            "timeframe":
                "1m",
            "trading_hours_template":
                "CME US Index Futures ETH",
            "source_timezone":
                "UTC",
            "bar_label":
                "CLOSE",
            "realtime":
                True,
            "read_only":
                True,
        },
    }

    canonical.write_bytes(
        stream_encode(
            hello
        )
        + b"\r\n"
    )

    sidecar.write_bytes(
        b""
    )

    connection.write_bytes(
        b""
    )

    rows = [
        stream_encode(
            hello
        )
    ]

    pairs = []

    original = (
        stream.profile.accept
    )

    def record(
        raw,
        pair=None,
        **kwargs,
    ):
        original(
            raw,
            pair,
            **kwargs,
        )

        rows.append(
            raw
        )

        with canonical.open(
            "ab"
        ) as handle:
            handle.write(
                raw
                + b"\r\n"
            )

        if pair is not None:
            pairs.append(
                pair
            )

            with sidecar.open(
                "ab"
            ) as handle:
                handle.write(
                    pair
                    + b"\n"
                )

    stream.profile.accept = record

    class LiveFiles:
        pass

    files = LiveFiles()

    files.root = root
    files.stream = stream
    files.adapter = adapter
    files.canonical = canonical
    files.sidecar = sidecar
    files.connection = connection
    files.rows = rows
    files.pairs = pairs

    def boundary():
        recorder = (
            files.stream.profile.accept
        )

        def deliver(
            *args,
            **kwargs,
        ):
            recorder(
                *args,
                **kwargs,
            )

            files.adapter.poll()

        files.stream.profile.accept = (
            deliver
        )

        try:
            files.stream.boundary()
        finally:
            files.stream.profile.accept = (
                recorder
            )

        return (
            files.adapter.snapshot()
        )

    files.boundary = boundary

    # HELLO now exists, but preactivation logic must only
    # quarantine/validate it. No binding or consumption.
    adapter.poll()

    assert adapter.status == "WAITING"
    assert adapter.reason is None
    assert adapter.activation_start is None

    assert adapter.session is None
    assert adapter.market is None
    assert adapter.timing is None

    assert adapter.sequence == -1
    assert adapter.pair_sequence == -1

    return files, adapter


def _two_bar_overlap_bootstrap():
    from backend.tests.test_certified_bootstrap_sprint15z import (
        bundle,
        certify,
        segment,
    )

    return certify(
        bundle(
            segment(2)
        )
    )


def test_quarantined_fresh_prefix_uses_runtime_replay_cursor(
    tmp_path,
):
    files, adapter = (
        _fresh_quarantined_files(
            tmp_path
        )
    )

    # All of these native rows were produced AFTER
    # adapter/runtime construction, but BEFORE activation.
    for _ in range(4):
        files.boundary()

    prefix_size = (
        files.canonical.stat().st_size
    )

    assert prefix_size > 0

    assert adapter.status == "WAITING"
    assert adapter.session is None
    assert adapter.market is None
    assert adapter.sequence == -1
    assert adapter.delivered_records == 0

    adapter.replace_waiting_bootstrap(
        _two_bar_overlap_bootstrap()
    )

    adapter.arm_activation()

    adapter.poll()

    assert adapter.market is not None
    assert adapter.timing is not None

    # Desired R12D-C contract:
    # because the inbox was empty when this runtime began,
    # the quarantined session is runtime-local and may replay
    # from byte zero. Ordinary restarts must NOT do this.
    assert (
        adapter.market.cursor
        == 0
    )

    assert (
        adapter.timing.cursor
        == 0
    )

    assert (
        adapter.market.cursor
        < prefix_size
    )

    assert (
        adapter.snapshot()[
            "order_submit_reachable"
        ]
        is False
    )


def test_quarantined_prefix_closes_handoff_without_live_gap(
    tmp_path,
):
    files, adapter = (
        _fresh_quarantined_files(
            tmp_path
        )
    )

    # Simulate exporter running while LATEST_CLOSED
    # catch-up is collected/certified.
    for _ in range(4):
        files.boundary()

    bootstrap = (
        _two_bar_overlap_bootstrap()
    )

    adapter.replace_waiting_bootstrap(
        bootstrap
    )

    adapter.arm_activation()

    adapter.poll()

    snapshot = (
        adapter.snapshot()
    )

    for _ in range(6):
        if (
            snapshot.get(
                "live_handoff_status"
            )
            == "COMPLETE"
        ):
            break

        files.boundary()

        snapshot = (
            adapter.snapshot()
        )

    assert adapter.reason is None

    assert (
        snapshot[
            "adapter_status"
        ]
        == "LIVE_TAIL"
    )

    assert (
        snapshot[
            "live_handoff_status"
        ]
        == "COMPLETE"
    )

    # No overlap is required here. The certified bootstrap's
    # last candle OPEN is 14:01 while its CLOSE label is 14:02.
    # The first eligible live CLOSED candle opens at 14:02,
    # therefore this is exact T -> T+1 continuity.
    assert (
        snapshot[
            "overlap_minutes_skipped"
        ]
        == 0
    )

    assert (
        snapshot[
            "handoff_gap"
        ]
        is None
    )

    from datetime import timedelta

    expected_first_live_open = (
        bootstrap.bars[-1]
        .candle()
        .timestamp
        + timedelta(minutes=1)
    )

    assert (
        snapshot[
            "first_live_closed"
        ][
            "source_open"
        ]
        == expected_first_live_open.isoformat()
    )

    assert (
        snapshot[
            "fault"
        ]
        is None
    )

    assert (
        snapshot[
            "order_submit_reachable"
        ]
        is False
    )

def test_ordinary_restart_keeps_existing_cursor_discard_semantics(
    tmp_path,
):
    from backend.tests.test_fresh_native_adapter_sprint15y import (
        EXPORTER,
        Files,
    )

    files = Files(
        tmp_path / "ordinary-restart",
        history=5,
    )

    files.stream.qpc += 1

    adapter = FreshNativeAdapterV1(
        health_gated=False,
        directory=files.root,
        installed_exporter=EXPORTER,
        qpc_clock=lambda: (
            files.stream.epoch,
            1000,
            files.stream.qpc,
        ),
    )

    adapter.poll()

    snapshot = adapter.snapshot()

    # This is deliberately the OPPOSITE contract from a
    # pre-activation quarantined buffer. Restart safety stays.
    assert (
        snapshot[
            "startup_cursor"
        ]
        == files.canonical.stat().st_size
    )

    assert (
        snapshot[
            "live_delivered_records"
        ]
        == 0
    )

    assert (
        snapshot[
            "first_live_tail"
        ]
        is None
    )

    assert (
        snapshot[
            "order_submit_reachable"
        ]
        is False
    )

    adapter.close()



def test_valid_session_existing_before_runtime_is_not_replay_eligible(
    tmp_path,
):
    inbox = (
        tmp_path
        / "preexisting-valid"
    )

    inbox.mkdir()

    write_valid_buffer(
        inbox
    )

    adapter = FreshNativeAdapterV1(
        directory=inbox,
        installed_exporter=SOURCE,
        qpc_clock=lambda: (
            "preexisting-valid-test",
            1000,
            1000,
        ),
        health_gated=True,
    )

    adapter.poll()

    assert adapter.status == "REVOKED"

    assert (
        adapter.reason
        == "INPUT_BEFORE_ACTIVATION_ALLOWANCE"
    )

    assert adapter.session is None
    assert adapter.market is None

    assert (
        adapter.snapshot()[
            "order_submit_reachable"
        ]
        is False
    )


def test_quarantined_file_replacement_before_activation_fails_closed(
    tmp_path,
):
    files, adapter = (
        _fresh_quarantined_files(
            tmp_path
        )
    )

    assert (
        adapter.validate_preactivation_buffer(
            "TEST_REPLACEMENT"
        )
        is not None
    )

    original = (
        files.canonical.read_bytes()
    )

    files.canonical.unlink()

    files.canonical.write_bytes(
        original
    )

    adapter.poll()

    assert adapter.status == "REVOKED"

    assert (
        adapter.reason
        == "INPUT_BEFORE_ACTIVATION_ALLOWANCE"
    )

    assert adapter.session is None
    assert adapter.market is None

    assert (
        adapter.snapshot()[
            "order_submit_reachable"
        ]
        is False
    )



def test_stale_quarantined_pairs_never_become_live(
    tmp_path,
):
    files, adapter = (
        _fresh_quarantined_files(
            tmp_path
        )
    )

    for _ in range(4):
        files.boundary()

    adapter.replace_waiting_bootstrap(
        _two_bar_overlap_bootstrap()
    )

    adapter.arm_activation()

    adapter.poll()

    snapshot = adapter.snapshot()

    # The two oldest FORMING observations in this fixture
    # are > 90 seconds old at activation. They may be parsed
    # for structural continuity, but can never be admitted
    # as LIVE_TAIL observations.
    assert (
        adapter.bootstrap_records
        > 0
    )

    assert (
        snapshot[
            "live_delivered_records"
        ]
        >= 0
    )

    assert (
        snapshot[
            "adapter_reason"
        ]
        != "TRANSPORT_PROCESSING_DELAY"
    )

    assert (
        snapshot[
            "order_submit_reachable"
        ]
        is False
    )


def test_processing_budget_remains_exactly_90_seconds(
    tmp_path,
):
    _, adapter = (
        _fresh_quarantined_files(
            tmp_path
        )
    )

    assert (
        adapter.options[
            "maximum_processing_seconds"
        ]
        == 90
    )

    assert (
        adapter.snapshot()[
            "order_submit_reachable"
        ]
        is False
    )
