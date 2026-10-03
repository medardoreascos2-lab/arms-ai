"""Build a deterministic local Phase 5 staging package without deployment."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.phase4.build_manifest import (
    BuildManifest,
    generate_build_manifest,
    serialize_build_manifest,
)
from backend.phase4.package_validation import (
    PackageValidationReport,
    assemble_phase4_package,
)
from backend.phase4.staging_runtime import REQUIRED_STAGING_FEATURES


STAGING_SOURCE_ROOTS = (
    "backend/phase3",
    "backend/phase4",
    "backend/phase5",
)


def _git_sha(repository_root: Path) -> str:
    status = subprocess.run(
        ["git", "-C", str(repository_root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        raise RuntimeError("staging build requires a clean Git worktree")
    result = subprocess.run(
        ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def discover_staging_artifacts(repository_root: Path) -> tuple[str, ...]:
    root = repository_root.resolve(strict=True)
    artifacts = ["requirements.txt"]
    for relative_root in STAGING_SOURCE_ROOTS:
        source_root = root.joinpath(*relative_root.split("/"))
        if not source_root.is_dir() or source_root.is_symlink():
            raise ValueError(f"required staging source root is unavailable: {relative_root}")
        files = sorted(
            path.relative_to(root).as_posix()
            for path in source_root.rglob("*.py")
            if path.is_file() and "__pycache__" not in path.parts
        )
        if not files:
            raise ValueError(f"required staging source root is empty: {relative_root}")
        artifacts.extend(files)
    return tuple(sorted(artifacts))


def build_staging_package(
    repository_root: Path,
    destination_root: Path,
    *,
    source_git_sha: str,
) -> tuple[BuildManifest, PackageValidationReport]:
    root = repository_root.resolve(strict=True)
    manifest = generate_build_manifest(
        root,
        source_git_sha=source_git_sha,
        requirements_path="requirements.txt",
        artifact_paths=discover_staging_artifacts(root),
        enabled_features=REQUIRED_STAGING_FEATURES,
    )
    report = assemble_phase4_package(
        root,
        destination_root.resolve(strict=False),
        serialize_build_manifest(manifest),
    )
    for path in destination_root.resolve(strict=True).rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    return manifest, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--destination-root", type=Path, required=True)
    parser.add_argument("--git-sha")
    args = parser.parse_args()
    root = args.repository_root.resolve(strict=True)
    manifest, report = build_staging_package(
        root,
        args.destination_root,
        source_git_sha=args.git_sha or _git_sha(root),
    )
    print(
        "PHASE5_STAGING_PACKAGE_VALID "
        f"source={manifest.source_git_sha} manifest={report.manifest_sha256} "
        f"artifacts={report.artifact_count} bytes={report.total_artifact_bytes} "
        "deployment_authorized=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
