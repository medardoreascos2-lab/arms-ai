"""Scan a local Phase 5 staging package without external services."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.phase5.artifact_scan import scan_staging_package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    args = parser.parse_args()
    report = scan_staging_package(args.package_root.resolve(strict=True))
    if report.passed:
        print(
            "PHASE5_STATIC_SCAN_PASS "
            f"files={report.files_scanned} checks={len(report.checks)} "
            "external_scan_authorized=false"
        )
        return 0
    print(
        "PHASE5_STATIC_SCAN_FAIL "
        + ",".join(
            f"{item.check}:{item.path}:{item.line or 0}" for item in report.findings
        ),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
