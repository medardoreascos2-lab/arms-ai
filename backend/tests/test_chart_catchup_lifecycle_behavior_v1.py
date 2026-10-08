"""Execute the actual catchup bridge against deterministic C# doubles only."""
import json
import os
from pathlib import Path
import subprocess

import pytest

from tools.startup_chart_catchup_v1 import capture_status


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "integrations/ninjatrader/ArmsChartCatchupBridgeV1.cs"
HARNESS = ROOT / "backend/tests/fixtures/chart_catchup_lifecycle_behavior_v1.cs"
CSC = (
    Path(os.environ.get("WINDIR", "C:/Windows"))
    / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
)

EXPECTED_STATES = (
    "WAITING_FOR_LIVE_HELLO",
    "LIVE_HELLO_ACCEPTED",
    "ALIGNMENT_BAR_CAPTURED",
    "WAITING_FOR_SECOND_BAR_ADVANCE",
    "CAPTURE_STARTED",
    "CAPTURE_BODY_WRITTEN",
    "CAPTURE_SEAL_WRITTEN",
    "CAPTURE_COMPLETE",
)


@pytest.fixture(scope="module")
def bridge_binary(tmp_path_factory):
    if not CSC.is_file():
        pytest.fail("WINDOWS_FRAMEWORK_COMPILER_REQUIRED")

    folder = tmp_path_factory.mktemp("chart-catchup-lifecycle")
    executable = folder / "chart-catchup-lifecycle.exe"
    result = subprocess.run(
        [
            str(CSC),
            "/nologo",
            "/langversion:5",
            "/target:exe",
            "/out:" + str(executable),
            "/r:System.Core.dll",
            "/r:System.Web.Extensions.dll",
            "/r:System.ComponentModel.DataAnnotations.dll",
            str(SOURCE),
            str(HARNESS),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0 and executable.is_file(), (
        result.stdout + result.stderr
    )
    return executable


def test_actual_csharp_bridge_lifecycle_is_aligned_one_shot_and_exact(
    bridge_binary,
    tmp_path,
):
    output = tmp_path / "capture"
    live = tmp_path / "live"
    result = subprocess.run(
        [str(bridge_binary), str(output), str(live)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report == {
        "classification": "SYNTHETIC_CSHARP_BEHAVIOR_NO_NINJATRADER_RUNTIME",
        "alignment": True,
        "terminate_recreate": True,
        "states": list(EXPECTED_STATES),
        "captures": 1,
        "real_native_api_calls": 0,
        "order_calls": 0,
    }

    lifecycle = output / "catchup-lifecycle.jsonl"
    rows = [json.loads(line) for line in lifecycle.read_text().splitlines()]
    assert tuple(row["state"] for row in rows) == EXPECTED_STATES
    assert [row["sequence"] for row in rows] == list(range(len(rows)))
    assert all(row["observation_only"] is True for row in rows)
    assert all(row["runtime_admission"] is False for row in rows)
    assert all(row["execution_authority"] is False for row in rows)
    assert capture_status(output) == "READY"


def test_actual_csharp_bridge_rejects_unterminated_predecessor_with_seal(
    bridge_binary,
    tmp_path,
):
    output = tmp_path / "capture"
    live = tmp_path / "live"
    result = subprocess.run(
        [str(bridge_binary), str(output), str(live), "unterminated"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report == {
        "classification": "SYNTHETIC_CSHARP_BEHAVIOR_NO_NINJATRADER_RUNTIME",
        "predecessor_rejected": True,
        "states": [
            "WAITING_FOR_LIVE_HELLO",
            "LIVE_HELLO_ACCEPTED",
            "ALIGNMENT_BAR_CAPTURED",
            "WAITING_FOR_SECOND_BAR_ADVANCE",
            "CAPTURE_VALIDATION_FAILED",
            "CAPTURE_FAILED",
        ],
        "captures": 0,
        "real_native_api_calls": 0,
        "order_calls": 0,
    }
    assert not list(output.glob("*.chart-catchup.jsonl"))
    with pytest.raises(
        ValueError,
        match="STARTUP_CATCHUP_CAPTURE_FAILED",
    ):
        capture_status(output)


def test_actual_csharp_bridge_resets_live_lineage_between_binding_generations(
    bridge_binary,
    tmp_path,
):
    output = tmp_path / "capture"
    live = tmp_path / "live"
    result = subprocess.run(
        [
            str(bridge_binary),
            str(output),
            str(live),
            "generation-rotation",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report == {
        "classification": "SYNTHETIC_CSHARP_BEHAVIOR_NO_NINJATRADER_RUNTIME",
        "consecutive_binding_generations": True,
        "first_states": list(EXPECTED_STATES),
        "second_states": list(EXPECTED_STATES),
        "captures": 2,
        "real_native_api_calls": 0,
        "order_calls": 0,
    }
