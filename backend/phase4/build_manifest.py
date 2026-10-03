"""Deterministic, secret-free Phase 4 build manifest generation."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile

from backend.phase3.durable_store import STORE_SCHEMA_VERSION

from .deployment_config import Phase4Feature
from .production_migrations import POSTGRES_SCHEMA_VERSION


BUILD_MANIFEST_FORMAT = "arms.phase4.build-manifest.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_DEPENDENCY = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9][A-Za-z0-9_.+!-]*)$"
)
_SENSITIVE_NAMES = frozenset({".env", "credentials.json", "secrets.json"})
_SENSITIVE_SUFFIXES = frozenset({".key", ".p12", ".pem"})


class BuildManifestError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class DependencyVersion:
    name: str
    version: str

    def __post_init__(self) -> None:
        match = _DEPENDENCY.fullmatch(f"{self.name}=={self.version}")
        if match is None:
            raise BuildManifestError("dependency must use an exact name==version pin")
        object.__setattr__(self, "name", match.group(1).lower().replace("_", "-"))


@dataclass(frozen=True, order=True)
class BuildArtifact:
    path: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        normalized = _artifact_path(self.path)
        if normalized != self.path:
            raise BuildManifestError("artifact path must be canonical POSIX relative text")
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise BuildManifestError("artifact size must be a nonnegative integer")
        if not isinstance(self.sha256, str) or _SHA256.fullmatch(self.sha256) is None:
            raise BuildManifestError("artifact sha256 must be a lowercase digest")


@dataclass(frozen=True)
class BuildManifest:
    source_git_sha: str
    phase3_schema_version: int
    phase4_migration_version: int
    dependency_versions: tuple[DependencyVersion, ...]
    feature_flags: tuple[str, ...]
    artifacts: tuple[BuildArtifact, ...]
    format: str = field(default=BUILD_MANIFEST_FORMAT, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    deployment_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_git_sha, str) or _GIT_SHA.fullmatch(
            self.source_git_sha
        ) is None:
            raise BuildManifestError("source_git_sha must be a full lowercase Git SHA")
        for name in ("phase3_schema_version", "phase4_migration_version"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise BuildManifestError(f"{name} must be a positive integer")
        if not isinstance(self.dependency_versions, tuple) or any(
            not isinstance(item, DependencyVersion) for item in self.dependency_versions
        ):
            raise BuildManifestError("dependency_versions must be an immutable tuple")
        if tuple(sorted(self.dependency_versions)) != self.dependency_versions:
            raise BuildManifestError("dependency_versions must be sorted")
        dependency_names = tuple(item.name for item in self.dependency_versions)
        if len(set(dependency_names)) != len(dependency_names):
            raise BuildManifestError("dependency names must be unique")
        if not isinstance(self.feature_flags, tuple) or tuple(
            sorted(set(self.feature_flags))
        ) != self.feature_flags:
            raise BuildManifestError("feature_flags must be sorted and unique")
        valid_flags = {item.value for item in Phase4Feature}
        if any(item not in valid_flags for item in self.feature_flags):
            raise BuildManifestError("feature_flags contain an unknown Phase4 feature")
        if not isinstance(self.artifacts, tuple) or any(
            not isinstance(item, BuildArtifact) for item in self.artifacts
        ):
            raise BuildManifestError("artifacts must be an immutable tuple")
        if tuple(sorted(self.artifacts)) != self.artifacts:
            raise BuildManifestError("artifacts must be sorted")
        paths = tuple(item.path for item in self.artifacts)
        if not paths or len(set(paths)) != len(paths):
            raise BuildManifestError("artifact paths must be nonempty and unique")

    @property
    def manifest_sha256(self) -> str:
        return hashlib.sha256(_canonical_payload(self)).hexdigest()


def _artifact_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise BuildManifestError("artifact path must be POSIX relative text")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise BuildManifestError("artifact path must remain within the repository")
    name = path.name.lower()
    if name in _SENSITIVE_NAMES or PurePosixPath(name).suffix in _SENSITIVE_SUFFIXES:
        raise BuildManifestError("sensitive artifact paths are forbidden")
    return path.as_posix()


def parse_dependency_versions(content: str) -> tuple[DependencyVersion, ...]:
    if not isinstance(content, str):
        raise BuildManifestError("requirements content must be text")
    dependencies: list[DependencyVersion] = []
    for line_number, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _DEPENDENCY.fullmatch(line)
        if match is None:
            raise BuildManifestError(
                f"requirement line {line_number} must use an exact name==version pin"
            )
        dependencies.append(DependencyVersion(match.group(1), match.group(2)))
    result = tuple(sorted(dependencies))
    if not result:
        raise BuildManifestError("at least one dependency version is required")
    if len({item.name for item in result}) != len(result):
        raise BuildManifestError("dependency names must be unique")
    return result


def generate_build_manifest(
    repository_root: Path,
    *,
    source_git_sha: str,
    requirements_path: str,
    artifact_paths: tuple[str, ...],
    enabled_features: frozenset[Phase4Feature],
) -> BuildManifest:
    if not isinstance(repository_root, Path) or not repository_root.is_absolute():
        raise BuildManifestError("repository_root must be an absolute Path")
    try:
        root = repository_root.resolve(strict=True)
    except OSError:
        raise BuildManifestError("repository_root is unavailable") from None
    if not root.is_dir():
        raise BuildManifestError("repository_root must be a directory")
    if not isinstance(enabled_features, frozenset) or any(
        not isinstance(item, Phase4Feature) for item in enabled_features
    ):
        raise BuildManifestError("enabled_features must be an immutable Phase4Feature set")
    requirements_relative = _artifact_path(requirements_path)
    requirements = _safe_file(root, requirements_relative)
    try:
        dependency_versions = parse_dependency_versions(
            requirements.read_text(encoding="utf-8")
        )
    except UnicodeDecodeError:
        raise BuildManifestError("requirements file must be UTF-8") from None

    artifacts: list[BuildArtifact] = []
    for raw_path in artifact_paths:
        relative = _artifact_path(raw_path)
        path = _safe_file(root, relative)
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    size += len(chunk)
                    digest.update(chunk)
        except OSError:
            raise BuildManifestError(f"artifact is unreadable: {relative}") from None
        artifacts.append(BuildArtifact(relative, size, digest.hexdigest()))

    return BuildManifest(
        source_git_sha=source_git_sha,
        phase3_schema_version=STORE_SCHEMA_VERSION,
        phase4_migration_version=POSTGRES_SCHEMA_VERSION,
        dependency_versions=dependency_versions,
        feature_flags=tuple(sorted(item.value for item in enabled_features)),
        artifacts=tuple(sorted(artifacts)),
    )


def _safe_file(root: Path, relative: str) -> Path:
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError):
        raise BuildManifestError(f"artifact is outside the repository: {relative}") from None
    if candidate.is_symlink() or not resolved.is_file():
        raise BuildManifestError(f"artifact must be a regular file: {relative}")
    return resolved


def _payload(manifest: BuildManifest) -> dict[str, object]:
    return {
        "format": manifest.format,
        "source_git_sha": manifest.source_git_sha,
        "phase3_schema_version": manifest.phase3_schema_version,
        "phase4_migration_version": manifest.phase4_migration_version,
        "dependency_versions": [
            {"name": item.name, "version": item.version}
            for item in manifest.dependency_versions
        ],
        "feature_flags": list(manifest.feature_flags),
        "artifacts": [
            {
                "path": item.path,
                "size_bytes": item.size_bytes,
                "sha256": item.sha256,
            }
            for item in manifest.artifacts
        ],
    }


def _canonical_payload(manifest: BuildManifest) -> bytes:
    return json.dumps(
        _payload(manifest),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def serialize_build_manifest(manifest: BuildManifest) -> bytes:
    if not isinstance(manifest, BuildManifest):
        raise BuildManifestError("manifest must be a BuildManifest")
    payload = _payload(manifest)
    payload["manifest_sha256"] = manifest.manifest_sha256
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("ascii")


def deserialize_build_manifest(data: bytes) -> BuildManifest:
    if not isinstance(data, bytes) or not data:
        raise BuildManifestError("manifest data must be nonempty bytes")
    try:
        raw = json.loads(data.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BuildManifestError("manifest must be canonical ASCII JSON") from None
    required = {
        "format",
        "source_git_sha",
        "phase3_schema_version",
        "phase4_migration_version",
        "dependency_versions",
        "feature_flags",
        "artifacts",
        "manifest_sha256",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise BuildManifestError("manifest fields are invalid")
    if raw["format"] != BUILD_MANIFEST_FORMAT:
        raise BuildManifestError("manifest format is unsupported")
    try:
        manifest = BuildManifest(
            source_git_sha=raw["source_git_sha"],
            phase3_schema_version=raw["phase3_schema_version"],
            phase4_migration_version=raw["phase4_migration_version"],
            dependency_versions=tuple(
                DependencyVersion(item["name"], item["version"])
                for item in raw["dependency_versions"]
            ),
            feature_flags=tuple(raw["feature_flags"]),
            artifacts=tuple(
                BuildArtifact(item["path"], item["size_bytes"], item["sha256"])
                for item in raw["artifacts"]
            ),
        )
    except (KeyError, TypeError, BuildManifestError, ValueError):
        raise BuildManifestError("manifest content is invalid") from None
    if raw["manifest_sha256"] != manifest.manifest_sha256:
        raise BuildManifestError("manifest checksum mismatch")
    if serialize_build_manifest(manifest) != data:
        raise BuildManifestError("manifest is not canonical")
    return manifest


def write_build_manifest(path: Path, manifest: BuildManifest) -> None:
    if not isinstance(path, Path) or not path.is_absolute():
        raise BuildManifestError("output path must be absolute")
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_symlink():
        raise BuildManifestError("output path cannot be a symlink")
    data = serialize_build_manifest(manifest)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".build-manifest-", dir=parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        raise BuildManifestError("build manifest could not be written") from None
    finally:
        temporary.unlink(missing_ok=True)
