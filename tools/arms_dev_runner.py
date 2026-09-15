#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
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



def command_batch(batch_file):
    """
    Execute one authorized ARMS AI development batch.

    The batch manifest is JSON and may contain:

    {
      "name": "example",
      "base_head": "<required git HEAD>",
      "allowed_files": ["path/a.py", "path/test_a.py"],
      "operations": [
        {
          "type": "write",
          "path": "path/a.py",
          "content": "..."
        }
      ],
      "full_backend": false
    }

    Safety:
    - exact branch
    - exact base HEAD
    - clean tracked worktree before application
    - no staged content
    - paths restricted to repository
    - modifications restricted to allowed_files
    - automatic rollback on application/test failure
    - no git add
    - no commit
    - no push
    """
    started = time.time()

    manifest_path = Path(batch_file)

    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path

    if not manifest_path.exists():
        print("STATUS=BLOCKED_BATCH_NOT_FOUND")
        print(f"BATCH={manifest_path}")
        return 1

    try:
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        print("STATUS=BLOCKED_INVALID_BATCH_JSON")
        print(f"ERROR={exc}")
        return 1

    name = str(manifest.get("name", "")).strip()
    base_head = str(manifest.get("base_head", "")).strip()
    allowed = manifest.get("allowed_files", [])
    operations = manifest.get("operations", [])
    full_backend = bool(
        manifest.get("full_backend", False)
    )

    if not name:
        print("STATUS=BLOCKED_BATCH_NAME_MISSING")
        return 1

    if not base_head:
        print("STATUS=BLOCKED_BASE_HEAD_MISSING")
        return 1

    if not isinstance(allowed, list) or not allowed:
        print("STATUS=BLOCKED_ALLOWED_FILES_MISSING")
        return 1

    if not isinstance(operations, list) or not operations:
        print("STATUS=BLOCKED_OPERATIONS_MISSING")
        return 1

    allowed = {
        Path(str(x)).as_posix()
        for x in allowed
    }

    info = baseline()

    if info["branch"] != BRANCH:
        print("STATUS=BLOCKED_WRONG_BRANCH")
        return 1

    if info["head"] != base_head:
        print("STATUS=BLOCKED_BASE_HEAD_CHANGED")
        print(f"EXPECTED={base_head}")
        print(f"ACTUAL={info['head']}")
        return 1

    if info["staged"] != 0:
        print("STATUS=BLOCKED_STAGED_CONTENT")
        return 1

    if info["tracked_dirty"] != 0:
        print("STATUS=BLOCKED_TRACKED_WORKTREE")
        return 1

    if info["diff_check"] != 0:
        print("STATUS=BLOCKED_DIFF_CHECK")
        return 1

    backup_root = (
        STATE
        / "backups"
        / f"{name}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    backup_root.mkdir(parents=True, exist_ok=True)

    original_state = {}

    def safe_path(relative):
        relative = Path(str(relative)).as_posix()

        if relative not in allowed:
            raise RuntimeError(
                f"unauthorized_file:{relative}"
            )

        candidate = (ROOT / relative).resolve()

        try:
            candidate.relative_to(ROOT.resolve())
        except ValueError:
            raise RuntimeError(
                f"path_escape:{relative}"
            )

        return relative, candidate

    try:
        # Snapshot authorized files.
        for relative in allowed:
            rel, target = safe_path(relative)

            if target.exists():
                original_state[rel] = True

                backup = backup_root / rel
                backup.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                shutil.copy2(target, backup)
            else:
                original_state[rel] = False

        # Apply authorized operations.
        for operation in operations:
            if not isinstance(operation, dict):
                raise RuntimeError(
                    "invalid_operation"
                )

            op_type = str(
                operation.get("type", "")
            ).strip()

            relative, target = safe_path(
                operation.get("path", "")
            )

            if op_type == "write":
                content = operation.get("content")

                if not isinstance(content, str):
                    raise RuntimeError(
                        f"invalid_content:{relative}"
                    )

                target.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                target.write_text(
                    content,
                    encoding="utf-8",
                    newline="\n",
                )

            elif op_type == "delete":
                if target.exists():
                    if target.is_dir():
                        raise RuntimeError(
                            f"directory_delete_forbidden:{relative}"
                        )
                    target.unlink()

            else:
                raise RuntimeError(
                    f"unsupported_operation:{op_type}"
                )

        # Verify actual tracked/untracked delta is inside boundary.
        after_files = set(changed_files())

        relevant_after = {
            x for x in after_files
            if x in allowed
        }

        unauthorized_tracked = []

        tracked_output = git(
            "status",
            "--short",
            "--untracked-files=no",
        )

        for line in tracked_output.splitlines():
            if not line.strip():
                continue

            filename = line[3:].strip()

            if filename not in allowed:
                unauthorized_tracked.append(
                    filename
                )

        if unauthorized_tracked:
            raise RuntimeError(
                "unauthorized_tracked_changes:"
                + ",".join(unauthorized_tracked)
            )

        if not relevant_after:
            raise RuntimeError(
                "batch_produced_no_changes"
            )

        diff_check = execute(
            ["git", "diff", "--check"]
        )

        if diff_check.returncode != 0:
            raise RuntimeError(
                "diff_check_failed:\n"
                + (diff_check.stdout or "")
            )

        tests = select_tests(
            sorted(relevant_after)
        )

        test_output = ""

        if tests:
            print(f"AUTO_TESTS={len(tests)}")
            print("PHASE=RELATED_TESTS")

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

            test_output = related.stdout or ""
            print(test_output)

            if related.returncode != 0:
                raise RuntimeError(
                    "related_tests_failed"
                )

        full_output = ""

        if full_backend:
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

            full_output = full.stdout or ""
            print(full_output)

            if full.returncode != 0:
                raise RuntimeError(
                    "full_backend_failed"
                )

        content = (
            f"BATCH={name}\n"
            f"BASE_HEAD={base_head}\n"
            f"ALLOWED_FILES={len(allowed)}\n"
            f"CHANGED_FILES={len(relevant_after)}\n"
            f"AUTO_TESTS={len(tests)}\n"
            f"FULL_BACKEND={full_backend}\n\n"
            "CHANGED\n"
            "========================================\n"
            + "\n".join(sorted(relevant_after))
            + "\n\nRELATED TEST OUTPUT\n"
            "========================================\n"
            + (test_output or "NONE")
            + "\n\nFULL BACKEND OUTPUT\n"
            "========================================\n"
            + (full_output or "NOT_REQUESTED")
        )

        report = save_report(
            "BATCH",
            "GREEN",
            content,
            started,
        )

        print("STATUS=GREEN")
        print(f"BATCH={name}")
        print(
            f"CHANGED_FILES={len(relevant_after)}"
        )
        print(f"AUTO_TESTS={len(tests)}")
        print(
            f"FULL_BACKEND={'YES' if full_backend else 'NO'}"
        )
        print(f"REPORT={report.relative_to(ROOT)}")
        print("GIT_ADD=NO")
        print("COMMIT=NO")
        print("PUSH=NO")

        return 0

    except Exception as exc:
        # Roll back only files authorized by this batch.
        for relative, existed in original_state.items():
            target = ROOT / relative
            backup = backup_root / relative

            if existed:
                target.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                shutil.copy2(backup, target)
            else:
                if target.exists() and target.is_file():
                    target.unlink()

        content = (
            f"BATCH={name}\n"
            f"BASE_HEAD={base_head}\n"
            f"ERROR={exc}\n"
            "ROLLBACK=APPLIED\n"
        )

        report = save_report(
            "BATCH",
            "BLOCKED",
            content,
            started,
        )

        print("STATUS=BLOCKED")
        print(f"ERROR={exc}")
        print("ROLLBACK=APPLIED")
        print(f"REPORT={report.relative_to(ROOT)}")
        print("GIT_ADD=NO")
        print("COMMIT=NO")
        print("PUSH=NO")

        return 1

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
            "batch",
        ],
    )

    parser.add_argument(
        "batch_file",
        nargs="?",
        help="JSON batch manifest for the batch command",
    )

    args = parser.parse_args()

    if args.command == "batch":
        if not args.batch_file:
            parser.error(
                "batch requires a JSON manifest"
            )
        return command_batch(args.batch_file)

    commands = {
        "status": command_status,
        "run": command_run,
        "certify": command_certify,
        "report": command_report,
    }

    return commands[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
