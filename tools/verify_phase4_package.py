"""Verify an assembled Phase 4 package without starting any runtime."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.phase4.package_validation import validate_phase4_package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    args = parser.parse_args()
    report = validate_phase4_package(args.package_root.resolve(strict=True))
    print(
        f"PHASE4_PACKAGE_VALID manifest={report.manifest_sha256} "
        f"artifacts={report.artifact_count} bytes={report.total_artifact_bytes}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
