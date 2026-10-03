"""Offline reconstruction and hash verification for Phase 5 staging packages."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path

from backend.phase4.package_validation import (
    PACKAGE_MANIFEST_FILENAME,
    PackageValidationError,
    assemble_phase4_package,
    validate_phase4_package,
)


class StagingPackageVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class StagingPackageVerificationReport:
    manifest_sha256: str
    package_sha256: str
    artifact_count: int
    total_artifact_bytes: int
    reconstructed: bool
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    deployment_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        for name in ("manifest_sha256", "package_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64:
                raise ValueError(f"{name} must be a SHA-256 digest")
        if type(self.artifact_count) is not int or self.artifact_count < 1:
            raise ValueError("artifact_count must be positive")
        if type(self.total_artifact_bytes) is not int or self.total_artifact_bytes < 0:
            raise ValueError("total_artifact_bytes must be nonnegative")
        if self.reconstructed is not True:
            raise ValueError("a verification report requires reconstruction")


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
    except ValueError:
        return False
    return True


def _package_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    files = tuple(sorted(path for path in root.rglob("*") if path.is_file()))
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        size = path.stat().st_size
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(size.to_bytes(8, "big"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def verify_reconstructable_staging_package(
    package_root: Path,
    reconstruction_root: Path,
) -> StagingPackageVerificationReport:
    if not isinstance(package_root, Path) or not package_root.is_absolute():
        raise StagingPackageVerificationError("package_root must be an absolute Path")
    if not isinstance(reconstruction_root, Path) or not reconstruction_root.is_absolute():
        raise StagingPackageVerificationError(
            "reconstruction_root must be an absolute Path"
        )
    try:
        source = package_root.resolve(strict=True)
        destination = reconstruction_root.resolve(strict=False)
    except OSError:
        raise StagingPackageVerificationError("package paths are unavailable") from None
    if not source.is_dir() or source.is_symlink():
        raise StagingPackageVerificationError("package_root must be a regular directory")
    if _is_within(destination, source) or _is_within(source, destination):
        raise StagingPackageVerificationError(
            "reconstruction_root must be separate from package_root"
        )
    if destination.exists() or destination.is_symlink():
        raise StagingPackageVerificationError("reconstruction_root must not exist")

    try:
        original = validate_phase4_package(source)
        manifest_data = (source / PACKAGE_MANIFEST_FILENAME).read_bytes()
        reconstructed = assemble_phase4_package(source, destination, manifest_data)
        original_hash = _package_sha256(source)
        reconstructed_hash = _package_sha256(destination)
    except (OSError, PackageValidationError) as exc:
        raise StagingPackageVerificationError(
            "staging package reconstruction failed"
        ) from exc

    if original != reconstructed or original_hash != reconstructed_hash:
        raise StagingPackageVerificationError("reconstructed package hash mismatch")
    for path in destination.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    return StagingPackageVerificationReport(
        manifest_sha256=original.manifest_sha256,
        package_sha256=original_hash,
        artifact_count=original.artifact_count,
        total_artifact_bytes=original.total_artifact_bytes,
        reconstructed=True,
    )
