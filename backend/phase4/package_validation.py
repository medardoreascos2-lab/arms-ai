"""Allowlisted Phase 4 package assembly and offline integrity validation."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path, PurePosixPath
import shutil
import tempfile

from .build_manifest import (
    BuildManifest,
    BuildManifestError,
    deserialize_build_manifest,
    serialize_build_manifest,
)


PACKAGE_MANIFEST_FILENAME = "phase4-build-manifest.json"


class PackageValidationError(ValueError):
    pass


@dataclass(frozen=True)
class PackageValidationReport:
    manifest_sha256: str
    artifact_count: int
    total_artifact_bytes: int
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    deployment_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if type(self.artifact_count) is not int or self.artifact_count < 1:
            raise ValueError("artifact_count must be positive")
        if type(self.total_artifact_bytes) is not int or self.total_artifact_bytes < 0:
            raise ValueError("total_artifact_bytes must be nonnegative")


def _root(path: Path, name: str, *, must_exist: bool) -> Path:
    if not isinstance(path, Path) or not path.is_absolute():
        raise PackageValidationError(f"{name} must be an absolute Path")
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError:
        raise PackageValidationError(f"{name} is unavailable") from None
    if must_exist and not resolved.is_dir():
        raise PackageValidationError(f"{name} must be a directory")
    return resolved


def _artifact_file(root: Path, relative: str) -> Path:
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError):
        raise PackageValidationError(f"package artifact is unavailable: {relative}") from None
    if candidate.is_symlink() or not resolved.is_file():
        raise PackageValidationError(f"package artifact must be a regular file: {relative}")
    return resolved


def _verify_artifacts(root: Path, manifest: BuildManifest) -> int:
    total = 0
    for artifact in manifest.artifacts:
        path = _artifact_file(root, artifact.path)
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    size += len(chunk)
                    digest.update(chunk)
        except OSError:
            raise PackageValidationError(
                f"package artifact is unreadable: {artifact.path}"
            ) from None
        if size != artifact.size_bytes or digest.hexdigest() != artifact.sha256:
            raise PackageValidationError(
                f"package artifact integrity mismatch: {artifact.path}"
            )
        total += size
    return total


def validate_phase4_package(package_root: Path) -> PackageValidationReport:
    root = _root(package_root, "package_root", must_exist=True)
    manifest_path = root / PACKAGE_MANIFEST_FILENAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise PackageValidationError("package manifest is unavailable")
    try:
        manifest = deserialize_build_manifest(manifest_path.read_bytes())
    except (OSError, BuildManifestError) as exc:
        raise PackageValidationError("package manifest is invalid") from exc
    if any(item.path == PACKAGE_MANIFEST_FILENAME for item in manifest.artifacts):
        raise PackageValidationError("package manifest cannot list itself as an artifact")
    total = _verify_artifacts(root, manifest)

    expected = {item.path for item in manifest.artifacts}
    expected.add(PACKAGE_MANIFEST_FILENAME)
    actual: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PackageValidationError("package cannot contain symlinks")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != expected:
        raise PackageValidationError("package files do not match the manifest allowlist")
    return PackageValidationReport(
        manifest.manifest_sha256,
        len(manifest.artifacts),
        total,
    )


def assemble_phase4_package(
    source_root: Path,
    destination_root: Path,
    manifest_data: bytes,
) -> PackageValidationReport:
    source = _root(source_root, "source_root", must_exist=True)
    if not isinstance(destination_root, Path) or not destination_root.is_absolute():
        raise PackageValidationError("destination_root must be an absolute Path")
    parent = _root(destination_root.parent, "destination parent", must_exist=True)
    destination = parent / destination_root.name
    if destination.exists() or destination.is_symlink():
        raise PackageValidationError("destination_root must not already exist")
    try:
        manifest = deserialize_build_manifest(manifest_data)
    except BuildManifestError as exc:
        raise PackageValidationError("package manifest is invalid") from exc
    if any(item.path == PACKAGE_MANIFEST_FILENAME for item in manifest.artifacts):
        raise PackageValidationError("package manifest cannot list itself as an artifact")
    _verify_artifacts(source, manifest)

    temporary = Path(tempfile.mkdtemp(prefix=".phase4-package-", dir=parent))
    try:
        for artifact in manifest.artifacts:
            source_path = _artifact_file(source, artifact.path)
            target = temporary.joinpath(*PurePosixPath(artifact.path).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, target)
        (temporary / PACKAGE_MANIFEST_FILENAME).write_bytes(
            serialize_build_manifest(manifest)
        )
        report = validate_phase4_package(temporary)
        temporary.replace(destination)
        return report
    except (OSError, PackageValidationError):
        raise PackageValidationError("Phase 4 package assembly failed") from None
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
