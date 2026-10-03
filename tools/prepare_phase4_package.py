"""Assemble an allowlisted local Phase 4 package; never build or deploy it."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.phase4.package_validation import assemble_phase4_package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--destination-root", type=Path, required=True)
    args = parser.parse_args()
    report = assemble_phase4_package(
        args.source_root.resolve(strict=True),
        args.destination_root.resolve(strict=False),
        args.manifest.read_bytes(),
    )
    print(
        f"PHASE4_PACKAGE_VALID manifest={report.manifest_sha256} "
        f"artifacts={report.artifact_count} bytes={report.total_artifact_bytes}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
