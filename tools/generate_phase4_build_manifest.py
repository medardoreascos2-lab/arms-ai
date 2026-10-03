"""Generate a deterministic Phase 4 build manifest without building or deploying."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.phase4.build_manifest import generate_build_manifest, write_build_manifest
from backend.phase4.deployment_config import Phase4Feature


def _git_sha(repository_root: Path) -> str:
    status = subprocess.run(
        ["git", "-C", str(repository_root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        raise RuntimeError("build manifest requires a clean Git worktree")
    result = subprocess.run(
        ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requirements", default="requirements.txt")
    parser.add_argument("--artifact", action="append", required=True)
    parser.add_argument(
        "--feature",
        action="append",
        default=[],
        choices=sorted(item.value for item in Phase4Feature),
    )
    parser.add_argument("--git-sha")
    args = parser.parse_args()
    root = args.repository_root.resolve(strict=True)
    manifest = generate_build_manifest(
        root,
        source_git_sha=args.git_sha or _git_sha(root),
        requirements_path=args.requirements,
        artifact_paths=tuple(args.artifact),
        enabled_features=frozenset(Phase4Feature(item) for item in args.feature),
    )
    write_build_manifest(args.output.resolve(strict=False), manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
