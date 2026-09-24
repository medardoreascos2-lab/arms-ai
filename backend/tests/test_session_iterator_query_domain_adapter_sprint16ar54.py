from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]

SOURCE = (
    ROOT
    / "integrations/ninjatrader/"
      "SessionIteratorQueryDomainAdapterV1.cs"
)

HARNESS = (
    ROOT
    / "backend/tests/fixtures/"
      "session_iterator_query_domain_adapter_harness_sprint16ar54.cs"
)

DESIGN = (
    ROOT
    / "docs/architecture/"
      "session_iterator_timestamp_domain_repair_sprint16ar54.md"
)

CSC = (
    Path(os.environ.get("WINDIR", "C:/Windows"))
    / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
)

SDK = Path("C:/Program Files/NinjaTrader 8/bin")

CASES = (
    "utc_identity",
    "central_unspecified",
    "r53_a",
    "r53_b",
    "r53_c",
    "r53_n",
    "invalid_dst",
    "ambiguous_dst",
    "local_rejected",
    "null_trading_hours",
    "null_timezone",
    "timezone_mutation",
    "range_rejected",
    "source_unchanged",
    "same_ticks_utc_relabel_not_repair",
    "invalid_provenance",
)


def checked(command, *, timeout=60):
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
    assert CSC.is_file(), (
        "WINDOWS_FRAMEWORK_COMPILER_REQUIRED"
    )

    folder = tmp_path_factory.mktemp(
        "r54-query-domain"
    )

    target = folder / "r54-query-domain.exe"

    checked(
        [
            CSC,
            "/nologo",
            "/langversion:5",
            "/target:exe",
            "/main:R54QueryDomainHarness",
            "/out:" + str(target),
            "/r:System.Core.dll",
            "/r:System.Web.Extensions.dll",
            SOURCE,
            HARNESS,
        ]
    )

    assert target.is_file()

    return target


def run_case(binary, *args):
    result = checked(
        [binary, *args],
        timeout=90,
    )

    payload = json.loads(result.stdout)

    assert (
        payload["classification"]
        == "SYNTHETIC_R54_QUERY_DOMAIN_ONLY"
    )

    assert payload["failed"] == 0
    assert payload["account_api_calls"] == 0
    assert payload["order_api_calls"] == 0
    assert payload["execution_authority"] is False

    return payload


@pytest.mark.parametrize("case", CASES)
def test_r54_runtime_case(binary, case):
    payload = run_case(
        binary,
        "--case",
        case,
    )

    assert payload["total"] == 1
    assert payload["passed"] == 1

    assert (
        payload["results"][0]["name"]
        == case
    )

    assert (
        payload["results"][0]["status"]
        == "PASS"
    )


def test_complete_runtime_inventory(binary):
    payload = run_case(binary, "--all")

    assert payload["total"] == len(CASES)
    assert payload["passed"] == len(CASES)

    assert tuple(
        row["name"]
        for row in payload["results"]
    ) == CASES


def test_source_preserves_repair_boundary():
    text = SOURCE.read_text(
        encoding="utf-8"
    )

    assert (
        "TimeZoneInfo.ConvertTimeToUtc"
        in text
    )

    assert ".IsInvalidTime(" in text
    assert ".IsAmbiguousTime(" in text

    assert (
        "DateTime.ToUniversalTime"
        not in text
    )

    assert (
        "TimeZoneInfo.Local"
        not in text
    )

    assert (
        "SOURCE_KIND_LOCAL_REJECTED"
        in text
    )

    assert (
        "TIMEZONE_CHANGED"
        in text
    )

    assert (
        "SOURCE_MUTATED"
        in text
    )


def test_no_trading_or_bars_mutation_surface():
    text = SOURCE.read_text(
        encoding="utf-8"
    )

    clean = re.sub(
        r"//[^\n]*|/\*.*?\*/",
        "",
        text,
        flags=re.S,
    )

    forbidden = (
        r"\b(Account|Order|Execution|"
        r"AtmStrategy|SubmitOrder|CreateOrder|"
        r"Position|Bars|Open|High|Low|Close|Volume)"
        r"\b"
    )

    assert not re.search(
        forbidden,
        clean,
    )

    assert ".Connect(" not in clean
    assert ".Disconnect(" not in clean


def test_design_regression_language_present():
    text = DESIGN.read_text(
        encoding="utf-8"
    )

    for token in (
        "C_U",
        "C_LUTC",
        "C_THUTC",
        "TradingHours.TimeZoneInfo",
        "No fallback to `DateTime.ToUniversalTime()`",
        "`LIVE_EXECUTION=NO`",
    ):
        assert token in text


def test_installed_sdk_compile_only(
    tmp_path,
):
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
        / "R54QueryDomainCompileOnly.dll"
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
            SOURCE,
        ]
    )

    assert target.is_file()
