"""R13L live/catch-up alignment contract; offline only, never orders."""
from pathlib import Path
import inspect

import tools.analysis_native_startup_v1 as startup
import tools.startup_chart_catchup_v1 as helper


CATCHUP = Path(
    "integrations/ninjatrader/"
    "ArmsChartCatchupBridgeV1.cs"
).read_text(
    encoding="utf-8"
)

LIVE = Path(
    "integrations/ninjatrader/"
    "ArmsReadOnlyMarketV1.cs"
).read_text(
    encoding="utf-8"
)

ADAPTER = Path(
    "backend/market_data/"
    "fresh_native_adapter_v1.py"
).read_text(
    encoding="utf-8"
)

PROFILE = Path(
    "backend/market_data/"
    "analysis_time_profile_v1.py"
).read_text(
    encoding="utf-8"
)


def method_slice(
    source,
    signature,
    next_signature=None,
):
    start = source.index(
        signature
    )

    if next_signature is None:
        return source[start:]

    end = source.index(
        next_signature,
        start + len(signature),
    )

    return source[start:end]


def test_latest_closed_has_explicit_live_quarantine_directory():
    assert (
        "public string LiveOutputDirectory"
        in CATCHUP
    )

    assert (
        'LiveOutputDirectory = "";'
        in CATCHUP
    )

    assert (
        "Live output directory"
        in CATCHUP
        or
        "Live quarantine directory"
        in CATCHUP
    )


def test_latest_closed_capture_is_deferred_to_realtime_bar_alignment():
    assert (
        "protected override void OnBarUpdate()"
        in CATCHUP
    )

    on_bar = method_slice(
        CATCHUP,
        "protected override void OnBarUpdate()",
        "private ",
    )

    for token in (
        "State != State.Realtime",
        "BarsInProgress != 0",
        "!IsFirstTickOfBar",
        "LiveHelloReady",
        "liveAlignmentBar",
        "CurrentBar",
        "Capture();",
    ):
        assert token in on_bar

    hello = on_bar.index(
        "LiveHelloReady"
    )

    anchor = on_bar.index(
        "liveAlignmentBar",
        hello,
    )

    capture = on_bar.index(
        "Capture();",
        anchor,
    )

    assert hello < anchor < capture

    assert (
        "CurrentBar <= liveAlignmentBar"
        in on_bar
        or
        "CurrentBar > liveAlignmentBar"
        in on_bar
    )


def test_live_exporter_conservative_closed_bar_rule_is_unchanged():
    assert (
        "CurrentBar - 1 > firstRealtimeBar"
        in LIVE
    )

    assert (
        'EmitTimedBar("CLOSED", Candle(1)'
        in LIVE
    )


def test_prepare_request_carries_live_quarantine_directory():
    source = inspect.getsource(
        helper.prepare_request
    )

    assert (
        "live_output_directory"
        in source
    )

    assert (
        "inbox"
        in source
    )

    assert (
        '"live_output_directory"'
        in source
    )


def test_startup_prints_alignment_directory_before_single_apply():
    source = inspect.getsource(
        startup.run
    )

    setup = source.index(
        "STARTUP_OPERATOR_SETUP_REQUIRED=TRUE"
    )

    action = source.index(
        "NINJATRADER_ACTION="
    )

    ready = source.index(
        "STARTUP_LIVE_QUARANTINE_READY=TRUE"
    )

    assert (
        "CATCHUP_LIVE_OUTPUT_DIRECTORY="
        in source[
            setup:ready
        ]
    )

    assert (
        setup
        < action
        < ready
    )

    assert (
        source.count(
            "NINJATRADER_ACTION="
        )
        == 1
    )


def test_prepared_request_pins_live_quarantine_directory():
    source = inspect.getsource(
        startup.perform_startup_chart_catchup
    )

    assert (
        "live_output_directory"
        in source
    )

    assert (
        "'inbox'"
        in source
        or
        '"inbox"'
        in source
    )

    assert (
        "STARTUP_CATCHUP_PREPARED_REQUEST"
        in source
    )


def test_alignment_contract_preserves_fail_closed_authorities():
    assert (
        "BOOTSTRAP_LIVE_GAP"
        in PROFILE
    )

    assert (
        "BOOTSTRAP_LIVE_OVERLAP_CONFLICT"
        in PROFILE
    )

    assert (
        "processing_seconds <= 90"
        in ADAPTER
    )

    assert (
        "SESSION_ROTATION"
        in ADAPTER
    )

    assert (
        "PREACTIVATION_BUFFER_IDENTITY"
        in ADAPTER
    )

    assert (
        "stale_quarantined_pair"
        in ADAPTER
    )

    combined = (
        CATCHUP
        + "\n"
        + LIVE
        + "\n"
        + ADAPTER
        + "\n"
        + PROFILE
        + "\n"
        + inspect.getsource(
            startup.perform_startup_chart_catchup
        )
        + "\n"
        + inspect.getsource(
            startup.run
        )
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
        assert forbidden not in combined
