#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".arms-dev"
REPORTS = STATE / "reports"
LATEST = STATE / "latest_report.txt"

BRANCH = "refactor/backend-architecture"

CERTIFIED_ENV = {
    "ARMS_MAXIMUM_OPEN_POSITIONS": "4",
    "ARMS_MAXIMUM_QUOTE_AGE_SECONDS": "5.0",
    "ARMS_MAXIMUM_SIGNAL_AGE_SECONDS": "30",
    "ARMS_MAXIMUM_SPREAD_POINTS": "5.0",
    "ARMS_MAXIMUM_STOP_POINTS": "50.0",
    "ARMS_MINIMUM_ATR_POINTS": "3.0",
    "ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE": "0.80",
    "ARMS_MINIMUM_A_PLUS_PROBABILITY": "0.80",
    "ARMS_MINIMUM_REWARD_RISK_RATIO": "2.0",
    "ARMS_MINIMUM_STOP_POINTS": "2.0",
    "ARMS_TRAILING_STOP_ACTIVATION_POINTS": "45.0",
    "ARMS_TRAILING_STOP_DISTANCE_POINTS": "15.0",
    "ARMS_TREND_FAST_PERIOD": "10",
    "ARMS_TREND_SLOW_PERIOD": "30",
    "ARMS_TREND_SLOPE_LOOKBACK": "5",
    "ARMS_TREND_SIDEWAYS_THRESHOLD_PERCENT": "0.0001",
    "ARMS_MARKET_CONTEXT_MINIMUM_CANDLES": "20",
    "ARMS_MARKET_CONTEXT_INTERNAL_RANGE_LOOKBACK": "10",
}


def execute(args, env=None):
    merged = os.environ.copy()
    if env:
        merged.update(env)

    return subprocess.run(
        args,
        cwd=ROOT,
        env=merged,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def git(*args):
    result = execute(["git", *args])

    if result.returncode:
        raise RuntimeError(result.stdout)

    return result.stdout.strip()


def changed_files():
    files = set()

    commands = [
        ("diff", "--name-only"),
        ("diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ]

    for command in commands:
        for line in git(*command).splitlines():
            if line.strip():
                files.add(line.strip())

    return sorted(files)


def select_tests(files):
    tests = set()
    test_root = ROOT / "backend" / "tests"

    for filename in files:
        path = Path(filename)

        if (
            filename.startswith("backend/tests/")
            and path.name.startswith("test_")
            and path.suffix == ".py"
        ):
            tests.add(filename)
            continue

        if not (
            filename.startswith("backend/")
            and path.suffix == ".py"
        ):
            continue

        stem = path.stem.replace("_v2", "")

        exact = test_root / f"test_{path.stem}.py"

        if exact.exists():
            tests.add(exact.relative_to(ROOT).as_posix())

        tokens = [
            x for x in stem.split("_")
            if len(x) >= 5
        ]

        for test in test_root.glob("test_*.py"):
            name = test.stem.lower()

            if any(token.lower() in name for token in tokens):
                tests.add(test.relative_to(ROOT).as_posix())

    return sorted(tests)


def baseline():
    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")

    staged = [
        x for x in
        git("diff", "--cached", "--name-only").splitlines()
        if x
    ]

    tracked = [
        x for x in
        git("status", "--short", "--untracked-files=no").splitlines()
        if x
    ]

    diff = execute(["git", "diff", "--check"])

    return {
        "branch": branch,
        "head": head,
        "staged": len(staged),
        "tracked_dirty": len(tracked),
        "diff_check": diff.returncode,
        "changed": changed_files(),
    }


def save_report(mode, status, content, started):
    REPORTS.mkdir(parents=True, exist_ok=True)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    report = REPORTS / f"ARMS_DEV_{mode}_{stamp}.txt"

    text = (
        "ARMS AI DEVELOPMENT RUNNER\n"
        "========================================\n"
        f"MODE={mode}\n"
        f"STATUS={status}\n"
        f"SECONDS={time.time() - started:.2f}\n\n"
        f"{content}\n"
    )

    report.write_text(text, encoding="utf-8")
    LATEST.write_text(text, encoding="utf-8")

    return report


def command_status():
    started = time.time()
    info = baseline()
    tests = select_tests(info["changed"])

    status = "GREEN"

    if info["branch"] != BRANCH:
        status = "BLOCKED_WRONG_BRANCH"
    elif info["diff_check"] != 0:
        status = "BLOCKED_DIFF_CHECK"

    content = (
        f"BRANCH={info['branch']}\n"
        f"HEAD={info['head']}\n"
        f"STAGED={info['staged']}\n"
        f"TRACKED_DIRTY={info['tracked_dirty']}\n"
        f"CHANGED_FILES={len(info['changed'])}\n"
        f"SELECTED_TESTS={len(tests)}\n\n"
        "CHANGED:\n"
        + ("\n".join(info["changed"]) or "NONE")
        + "\n\nAUTO_TESTS:\n"
        + ("\n".join(tests) or "NONE")
    )

    report = save_report(
        "STATUS",
        status,
        content,
        started,
    )

    print(f"STATUS={status}")
    print(f"HEAD={info['head']}")
    print(f"CHANGED_FILES={len(info['changed'])}")
    print(f"AUTO_TESTS={len(tests)}")
    print(f"REPORT={report.relative_to(ROOT)}")

    return 0 if status == "GREEN" else 1


def command_run():
    started = time.time()
    info = baseline()

    if info["branch"] != BRANCH:
        status = "BLOCKED_WRONG_BRANCH"
        report = save_report(
            "RUN",
            status,
            str(info),
            started,
        )
        print(f"STATUS={status}")
        print(f"REPORT={report.relative_to(ROOT)}")
        return 1

    if info["diff_check"] != 0:
        status = "BLOCKED_DIFF_CHECK"
        report = save_report(
            "RUN",
            status,
            str(info),
            started,
        )
        print(f"STATUS={status}")
        print(f"REPORT={report.relative_to(ROOT)}")
        return 1

    tests = select_tests(info["changed"])

    if not tests:
        status = "GREEN_NO_TESTS_SELECTED"

        report = save_report(
            "RUN",
            status,
            "No related tests detected.",
            started,
        )

        print(f"STATUS={status}")
        print("AUTO_TESTS=0")
        print(f"REPORT={report.relative_to(ROOT)}")
        return 0

    print(f"AUTO_TESTS={len(tests)}")
    print("PHASE=RELATED_TESTS")

    result = execute(
        [
            sys.executable,
            "-m",
            "pytest",
            *tests,
            "-q",
            "--disable-warnings",
            "--maxfail=1",
        ],
        env=CERTIFIED_ENV,
    )

    print(result.stdout)

    status = (
        "GREEN"
        if result.returncode == 0
        else "BLOCKED_RELATED_TEST"
    )

    content = (
        "SELECTED TESTS\n"
        "========================================\n"
        + "\n".join(tests)
        + "\n\n"
        "PYTEST OUTPUT\n"
        "========================================\n"
        + result.stdout
    )

    report = save_report(
        "RUN",
        status,
        content,
        started,
    )

    print(f"STATUS={status}")
    print(f"TEST_EXIT={result.returncode}")
    print(f"REPORT={report.relative_to(ROOT)}")

    return result.returncode


def command_certify():
    started = time.time()
    info = baseline()

    if info["branch"] != BRANCH:
        status = "BLOCKED_WRONG_BRANCH"

        report = save_report(
            "CERTIFY",
            status,
            str(info),
            started,
        )

        print(f"STATUS={status}")
        print(f"REPORT={report.relative_to(ROOT)}")
        return 1

    if info["diff_check"] != 0:
        status = "BLOCKED_DIFF_CHECK"

        report = save_report(
            "CERTIFY",
            status,
            str(info),
            started,
        )

        print(f"STATUS={status}")
        print(f"REPORT={report.relative_to(ROOT)}")
        return 1

    tests = select_tests(info["changed"])
    output_parts = []

    if tests:
        print(f"PHASE=RELATED_TESTS")
        print(f"AUTO_TESTS={len(tests)}")

        related = execute(
            [
                sys.executable,
                "-m",
                "pytest",
                *tests,
                "-q",
                "--disable-warnings",
                "--maxfail=1",
            ],
            env=CERTIFIED_ENV,
        )

        print(related.stdout)

        output_parts.append(
            "RELATED TESTS\n"
            "========================================\n"
            + related.stdout
        )

        if related.returncode != 0:
            status = "BLOCKED_RELATED_TEST"

            report = save_report(
                "CERTIFY",
                status,
                "\n\n".join(output_parts),
                started,
            )

            print(f"STATUS={status}")
            print(f"REPORT={report.relative_to(ROOT)}")
            return related.returncode

    print("PHASE=FULL_BACKEND")

    full = execute(
        [
            sys.executable,
            "-m",
            "pytest",
            "backend/tests",
            "-q",
            "--disable-warnings",
            "--maxfail=1",
        ],
        env=CERTIFIED_ENV,
    )

    print(full.stdout)

    output_parts.append(
        "FULL BACKEND\n"
        "========================================\n"
        + full.stdout
    )

    final_diff = execute(
        ["git", "diff", "--check"]
    )

    if full.returncode != 0:
        status = "BLOCKED_FULL_BACKEND"
    elif final_diff.returncode != 0:
        status = "BLOCKED_FINAL_DIFF"
    else:
        status = "GREEN"

    output_parts.append(
        "FINAL DIFF CHECK\n"
        "========================================\n"
        + (
            final_diff.stdout
            if final_diff.stdout
            else "GREEN"
        )
    )

    report = save_report(
        "CERTIFY",
        status,
        "\n\n".join(output_parts),
        started,
    )

    print(f"STATUS={status}")
    print(f"FULL_BACKEND_EXIT={full.returncode}")
    print(f"REPORT={report.relative_to(ROOT)}")

    return 0 if status == "GREEN" else 1


def command_report():
    if not LATEST.exists():
        print("NO_REPORT_AVAILABLE")
        return 1

    print(
        LATEST.read_text(
            encoding="utf-8"
        )
    )

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="ARMS AI semi-automatic development runner"
    )

    parser.add_argument(
        "command",
        choices=[
            "status",
            "run",
            "certify",
            "report",
        ],
    )

    args = parser.parse_args()

    commands = {
        "status": command_status,
        "run": command_run,
        "certify": command_certify,
        "report": command_report,
    }

    return commands[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
