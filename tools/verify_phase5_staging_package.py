"""Reconstruct and hash-check a Phase 5 staging package without deployment."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.phase5.package_verification import (
    StagingPackageVerificationError,
    verify_reconstructable_staging_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--reconstruction-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = verify_reconstructable_staging_package(
            args.package_root.resolve(strict=True),
            args.reconstruction_root.resolve(strict=False),
        )
    except (OSError, StagingPackageVerificationError) as exc:
        print(f"PHASE5_PACKAGE_VERIFICATION_FAIL {exc}", file=sys.stderr)
        return 1
    print(
        "PHASE5_PACKAGE_VERIFICATION_PASS "
        f"manifest={report.manifest_sha256} package={report.package_sha256} "
        f"artifacts={report.artifact_count} bytes={report.total_artifact_bytes} "
        "deployment_authorized=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
