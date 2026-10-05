"""R23C-R2 preactivation MarketV1 lineage regression tests.

Offline only. These tests create local observation files and never expose an
account, broker, PAPER, LIVE execution, or order submission surface.
"""

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import pytest

from backend.tests.test_preactivation_live_buffer_v1 import (
    HELLO_PAYLOAD,
    certified_bootstrap,
    encode,
    new_adapter,
)
from tools.startup_chart_catchup_v1 import capture_status


def _event_time(second):
    return f"2026-10-05T02:21:{second:02d}.0000000Z"


def _write_session(inbox, *, payload=None, hello_second=0):
    session = str(uuid4())
    hello = {
        "schema": "arms.nt.market.v1",
        "session": session,
        "sequence": 0,
        "event_time": _event_time(hello_second),
        "kind": "HELLO",
        "payload": dict(HELLO_PAYLOAD if payload is None else payload),
    }
    canonical = inbox / f"{session}.jsonl"
    canonical.write_bytes(encode(hello) + b"\n")
    (inbox / f"{session}.connection.jsonl").write_bytes(b"")
    return session


def _write_timing_seal(inbox, session, canonical_records):
    timing = inbox / "timing"
    timing.mkdir(exist_ok=True)
    sidecar = timing / f"{session}.production-timing.jsonl"
    sidecar.write_bytes(b"")
    seal = {
        "schema": "arms.nt.production-timing.seal.v1",
        "session": session,
        "records": 0,
        "bytes": 0,
        "sha256": sha256(b"").hexdigest(),
        "canonical_records": canonical_records,
        "canonical_writer_closed": True,
        "timing_writer_closed": True,
        "complete": True,
    }
    Path(str(sidecar) + ".done.json").write_bytes(encode(seal))


def _terminate_session(inbox, session, *, second=1):
    canonical = inbox / f"{session}.jsonl"
    rows = [json.loads(line) for line in canonical.read_text().splitlines()]
    rows.append({
        "schema": "arms.nt.market.v1",
        "session": session,
        "sequence": len(rows),
        "event_time": _event_time(second),
        "kind": "DISCONNECTED",
        "payload": {
            "connected": False,
            "reason": "TERMINATED",
            "error_code": "NONE",
        },
    })
    canonical.write_bytes(b"".join(encode(row) + b"\n" for row in rows))
    _write_timing_seal(inbox, session, len(rows))


def _assert_blocked(adapter):
    snapshot = adapter.snapshot()
    assert adapter.status == "REVOKED"
    assert adapter.activation_start is None
    assert adapter.session is None
    assert snapshot["order_submit_reachable"] is False


def test_forensic_terminate_recreate_is_one_quarantined_lineage(tmp_path):
    adapter, inbox, _ = new_adapter(tmp_path)
    predecessor = _write_session(inbox, hello_second=0)
    assert adapter.validate_preactivation_buffer("TEST_LINEAGE") == predecessor

    _terminate_session(inbox, predecessor, second=1)
    replacement = _write_session(inbox, hello_second=2)

    assert adapter.validate_preactivation_buffer("TEST_LINEAGE") == replacement
    assert adapter.preactivation_lineage_root == predecessor
    assert adapter.preactivation_lineage_sessions == (predecessor, replacement)
    assert adapter.status == "WAITING"
    assert adapter.activation_start is None
    assert adapter.session is None
    assert adapter.snapshot()["order_submit_reachable"] is False


def test_empty_replacement_waits_for_hello_without_activation(tmp_path):
    adapter, inbox, _ = new_adapter(tmp_path)
    predecessor = _write_session(inbox, hello_second=0)
    assert adapter.validate_preactivation_buffer("TEST_LINEAGE") == predecessor
    _terminate_session(inbox, predecessor, second=1)

    replacement = str(uuid4())
    canonical = inbox / f"{replacement}.jsonl"
    canonical.write_bytes(b"")
    (inbox / f"{replacement}.connection.jsonl").write_bytes(b"")

    assert adapter.validate_preactivation_buffer("TEST_LINEAGE") == predecessor
    assert adapter.preactivation_transition_pending is True
    assert adapter.activation_start is None
    assert adapter.session is None

    hello = {
        "schema": "arms.nt.market.v1",
        "session": replacement,
        "sequence": 0,
        "event_time": _event_time(2),
        "kind": "HELLO",
        "payload": dict(HELLO_PAYLOAD),
    }
    canonical.write_bytes(encode(hello) + b"\n")

    assert adapter.validate_preactivation_buffer("TEST_LINEAGE") == replacement
    assert adapter.preactivation_transition_pending is False
    assert adapter.activation_start is None
    assert adapter.snapshot()["order_submit_reachable"] is False


def test_third_physical_session_is_never_accepted(tmp_path):
    adapter, inbox, _ = new_adapter(tmp_path)
    predecessor = _write_session(inbox, hello_second=0)
    assert adapter.validate_preactivation_buffer("TEST_LINEAGE") == predecessor
    _terminate_session(inbox, predecessor, second=1)
    replacement = _write_session(inbox, hello_second=2)
    assert adapter.validate_preactivation_buffer("TEST_LINEAGE") == replacement
    _write_session(inbox, hello_second=3)

    adapter.poll()
    _assert_blocked(adapter)


def test_validated_replacement_is_leaf_bound_only_after_activation(tmp_path):
    adapter, inbox, _ = new_adapter(tmp_path)
    predecessor = _write_session(inbox, hello_second=0)
    assert adapter.validate_preactivation_buffer("TEST_LINEAGE") == predecessor
    _terminate_session(inbox, predecessor, second=1)
    replacement = _write_session(inbox, hello_second=2)
    assert adapter.validate_preactivation_buffer("TEST_LINEAGE") == replacement

    adapter.replace_waiting_bootstrap(certified_bootstrap())
    adapter.arm_activation()
    adapter.poll()

    assert adapter.reason is None
    assert adapter.session == replacement
    assert adapter.market.path == inbox / f"{replacement}.jsonl"
    assert adapter.snapshot()["order_submit_reachable"] is False


@pytest.mark.parametrize("field", ("provider", "contract"))
def test_replacement_with_changed_identity_fails_closed(tmp_path, field):
    adapter, inbox, _ = new_adapter(tmp_path)
    predecessor = _write_session(inbox, hello_second=0)
    assert adapter.validate_preactivation_buffer("TEST_LINEAGE") == predecessor
    _terminate_session(inbox, predecessor, second=1)
    changed = dict(HELLO_PAYLOAD)
    changed[field] = "DIFFERENT"
    _write_session(inbox, payload=changed, hello_second=2)

    adapter.poll()
    _assert_blocked(adapter)


def test_overlapping_active_replacement_fails_closed(tmp_path):
    adapter, inbox, _ = new_adapter(tmp_path)
    predecessor = _write_session(inbox, hello_second=0)
    assert adapter.validate_preactivation_buffer("TEST_LINEAGE") == predecessor
    _write_session(inbox, hello_second=2)

    adapter.poll()
    _assert_blocked(adapter)


def test_timing_seal_cannot_replace_predecessor_without_termination(tmp_path):
    adapter, inbox, _ = new_adapter(tmp_path)
    predecessor = _write_session(inbox, hello_second=0)
    assert adapter.validate_preactivation_buffer("TEST_LINEAGE") == predecessor
    _write_timing_seal(inbox, predecessor, canonical_records=1)
    _write_session(inbox, hello_second=2)

    adapter.poll()

    _assert_blocked(adapter)
    assert adapter.preactivation_lineage_sessions == (predecessor,)


def test_replacement_after_activation_allowance_fails_closed(tmp_path):
    adapter, inbox, _ = new_adapter(tmp_path)
    predecessor = _write_session(inbox, hello_second=0)
    assert adapter.validate_preactivation_buffer("TEST_LINEAGE") == predecessor
    adapter.replace_waiting_bootstrap(certified_bootstrap())
    adapter.arm_activation()

    _terminate_session(inbox, predecessor, second=1)
    _write_session(inbox, hello_second=2)
    adapter.poll()

    snapshot = adapter.snapshot()
    assert adapter.status == "REVOKED"
    assert adapter.session is None
    assert snapshot["order_submit_reachable"] is False


def test_partial_lifecycle_write_waits_for_complete_record(tmp_path):
    capture = tmp_path / "chart-catchup"
    capture.mkdir()
    diagnostic = capture / "catchup-lifecycle.jsonl"
    diagnostic.write_bytes(b"")

    assert capture_status(capture) == "WAITING"

    waiting = encode({
        "schema": "arms.nt.chart-catchup.lifecycle.v1",
        "sequence": 0,
        "event_time": _event_time(0),
        "state": "WAITING_FOR_LIVE_HELLO",
        "reason": None,
        "observation_only": True,
        "runtime_admission": False,
        "execution_authority": False,
    })
    diagnostic.write_bytes(waiting[:20])
    assert capture_status(capture) == "WAITING"

    diagnostic.write_bytes(waiting + b"\n")
    assert capture_status(capture) == "WAITING"


def test_catchup_terminal_failure_diagnostic_is_durable_and_fail_closed(tmp_path):
    capture = tmp_path / "chart-catchup"
    capture.mkdir()
    diagnostic = capture / "catchup-lifecycle.jsonl"
    states = (
        "WAITING_FOR_LIVE_HELLO",
        "LIVE_HELLO_ACCEPTED",
        "ALIGNMENT_BAR_CAPTURED",
        "WAITING_FOR_SECOND_BAR_ADVANCE",
        "CAPTURE_STARTED",
        "CAPTURE_VALIDATION_FAILED",
        "CAPTURE_FAILED",
    )
    diagnostic.write_bytes(b"".join(encode({
        "schema": "arms.nt.chart-catchup.lifecycle.v1",
        "sequence": sequence,
        "event_time": _event_time(sequence),
        "state": state,
        "reason": "INVALID_OPERATION" if state.endswith("FAILED") else None,
        "observation_only": True,
        "runtime_admission": False,
        "execution_authority": False,
    }) + b"\n" for sequence, state in enumerate(states)))

    with pytest.raises(ValueError, match="STARTUP_CATCHUP_CAPTURE_FAILED"):
        capture_status(capture)

    assert diagnostic.read_bytes().endswith(b"\n")


def test_bridge_source_declares_every_durable_lifecycle_state():
    source = Path("integrations/ninjatrader/ArmsChartCatchupBridgeV1.cs").read_text()
    for state in (
        "WAITING_FOR_LIVE_HELLO",
        "LIVE_HELLO_ACCEPTED",
        "ALIGNMENT_BAR_CAPTURED",
        "WAITING_FOR_SECOND_BAR_ADVANCE",
        "CAPTURE_STARTED",
        "CAPTURE_VALIDATION_FAILED",
        "CAPTURE_BODY_WRITTEN",
        "CAPTURE_SEAL_WRITTEN",
        "CAPTURE_COMPLETE",
        "CAPTURE_FAILED",
    ):
        assert state in source

    for forbidden in (
        "SubmitOrder",
        "CreateOrder(",
        "ChangeOrder",
        "CancelOrder",
        "EnterLong",
        "EnterShort",
    ):
        assert forbidden not in source


def test_current_ninjatrader_sdk_compiles_patched_bridge(tmp_path):
    framework = (
        Path(os.environ.get("WINDIR", "C:/Windows"))
        / "Microsoft.NET/Framework64/v4.0.30319"
    )
    sdk = Path("C:/Program Files/NinjaTrader 8/bin")
    custom = (
        Path.home()
        / "OneDrive/Documents/NinjaTrader 8/bin/Custom/NinjaTrader.Custom.dll"
    )
    compiler = framework / "csc.exe"
    if not compiler.is_file() or not custom.is_file() or not (sdk / "NinjaTrader.Core.dll").is_file():
        pytest.skip("installed NinjaTrader SDK required")

    authored = Path(
        "integrations/ninjatrader/ArmsChartCatchupBridgeV1.cs"
    ).read_text()
    source = tmp_path / "catchup.cs"
    source.write_text(
        "extern alias NTBase;\n"
        "using Indicator = "
        "NTBase::NinjaTrader.NinjaScript.Indicators.Indicator;\n"
        + authored,
        encoding="utf-8",
    )
    references = [
        sdk / "NinjaTrader.Core.dll",
        sdk / "NinjaTrader.Gui.dll",
        framework / "WPF/WindowsBase.dll",
        framework / "WPF/PresentationCore.dll",
        framework / "WPF/PresentationFramework.dll",
        "System.Core.dll",
        "System.Web.Extensions.dll",
        "System.ComponentModel.DataAnnotations.dll",
        "System.Xaml.dll",
    ]
    result = subprocess.run(
        [
            str(compiler),
            "/nologo",
            "/langversion:5",
            "/target:library",
            "/out:" + str(tmp_path / "catchup.dll"),
            *("/r:" + str(path) for path in references),
            "/r:NTBase=" + str(custom),
            str(source),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CS0436" not in result.stdout + result.stderr
