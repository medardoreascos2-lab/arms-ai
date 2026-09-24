from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]

ADAPTER = (
    ROOT
    / "integrations/ninjatrader/"
      "SessionIteratorQueryDomainAdapterV1.cs"
)

SOURCE = (
    ROOT
    / "integrations/ninjatrader/"
      "SessionIteratorQueryDomainNativeComparisonV1.cs"
)

HARNESS = (
    ROOT
    / "backend/tests/fixtures/"
      "session_iterator_query_domain_native_comparison_harness_sprint16ar54.cs"
)

CSC = (
    Path(os.environ.get("WINDIR", "C:/Windows"))
    / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
)

SDK = Path("C:/Program Files/NinjaTrader 8/bin")

CASES = (
    "normal_c_matrix",
    "null_bars",
    "null_trading_hours",
    "wrong_source_kind",
    "missing_checkpoint",
    "constructor_failure",
    "advance_failure",
    "invalid_bounds",
)


def checked(command, timeout=60):
    result = subprocess.run(
        [str(x) for x in command],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    assert result.returncode == 0, (
        result.stdout + result.stderr
    )

    return result


@pytest.fixture(scope="module")
def binary(tmp_path_factory):
    assert CSC.is_file()

    folder = tmp_path_factory.mktemp(
        "r54-native-comparison"
    )

    target = folder / "r54-native-comparison.exe"

    checked(
        [
            CSC,
            "/nologo",
            "/langversion:5",
            "/target:exe",
            "/main:R54NativeComparisonHarness",
            "/out:" + str(target),
            "/r:System.Core.dll",
            "/r:System.Web.Extensions.dll",
            ADAPTER,
            SOURCE,
            HARNESS,
        ]
    )

    assert target.is_file()

    return target


def run(binary, *args):
    result = checked(
        [binary, *args],
        timeout=90,
    )

    payload = json.loads(result.stdout)

    assert (
        payload["classification"]
        == "SYNTHETIC_R54_NATIVE_COMPARISON_ONLY"
    )

    assert payload["failed"] == 0
    assert payload["account_api_calls"] == 0
    assert payload["order_api_calls"] == 0
    assert payload["execution_authority"] is False

    return payload


@pytest.mark.parametrize("case", CASES)
def test_runtime_case(binary, case):
    payload = run(
        binary,
        "--case",
        case,
    )

    assert payload["total"] == 1
    assert payload["passed"] == 1
    assert payload["results"][0]["name"] == case
    assert payload["results"][0]["status"] == "PASS"


def test_complete_inventory(binary):
    payload = run(binary, "--all")

    assert payload["total"] == len(CASES)
    assert payload["passed"] == len(CASES)

    assert tuple(
        row["name"]
        for row in payload["results"]
    ) == CASES


def test_exact_three_way_comparison_contract():
    text = SOURCE.read_text(encoding="utf-8")

    for token in (
        '"C_RAW"',
        '"C_SAME_TICKS"',
        '"C_ADAPTER"',
        "SessionIteratorQueryDomainAdapterV1.Adapt",
        "new SessionIterator(bars)",
        "iterator.GetNextSession(query, true)",
        "source.Ticks == originalTicks",
        "constructors == 3",
        "calls == 3",
    ):
        assert token in text


def test_no_trading_file_or_connection_surface():
    text = SOURCE.read_text(encoding="utf-8")

    clean = re.sub(
        r"//[^\n]*|/\*.*?\*/",
        "",
        text,
        flags=re.S,
    )

    forbidden = (
        r"\b(Account|Order|Execution|AtmStrategy|"
        r"SubmitOrder|CreateOrder|Position|"
        r"File|Directory|StreamWriter|FileStream)"
        r"\b"
    )

    assert not re.search(forbidden, clean)

    assert ".Connect(" not in clean
    assert ".Disconnect(" not in clean
    assert "DateTime.ToUniversalTime" not in clean
    assert "TimeZoneInfo.Local" not in clean


def test_adapter_remains_separate_boundary():
    adapter = ADAPTER.read_text(encoding="utf-8")
    source = SOURCE.read_text(encoding="utf-8")

    assert "TimeZoneInfo.ConvertTimeToUtc" in adapter
    assert "TimeZoneInfo.ConvertTimeToUtc" not in source
    assert "SessionIteratorQueryDomainAdapterV1.Adapt" in source


def test_installed_sdk_compile_only(tmp_path):
    assert CSC.is_file()

    core = SDK / "NinjaTrader.Core.dll"
    gui = SDK / "NinjaTrader.Gui.dll"

    assert core.is_file()
    assert gui.is_file()

    windows_base = (
        CSC.parent
        / "WPF/WindowsBase.dll"
    )

    assert windows_base.is_file()

    target = (
        tmp_path
        / "R54NativeComparisonCompileOnly.dll"
    )

    checked(
        [
            CSC,
            "/nologo",
            "/langversion:5",
            "/target:library",
            "/out:" + str(target),
            "/r:System.Core.dll",
            "/r:" + str(core),
            "/r:" + str(gui),
            "/r:" + str(windows_base),
            ADAPTER,
            SOURCE,
        ]
    )

    assert target.is_file()
