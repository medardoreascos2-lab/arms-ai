"""R46C tests for allowlisted packaging with no runtime startup."""

from pathlib import Path
import subprocess
import sys

import pytest

from backend.phase4.build_manifest import (
    generate_build_manifest,
    serialize_build_manifest,
)
from backend.phase4.deployment_config import Phase4Feature
from backend.phase4.package_validation import (
    PACKAGE_MANIFEST_FILENAME,
    PackageValidationError,
    assemble_phase4_package,
    validate_phase4_package,
)


GIT_SHA = "2" * 40


def source_and_manifest(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "requirements.txt").write_text("fastapi==0.139.2\n", encoding="utf-8")
    (source / "backend").mkdir()
    (source / "backend" / "phase4.py").write_text("SAFE = True\n", encoding="utf-8")
    manifest = generate_build_manifest(
        source,
        source_git_sha=GIT_SHA,
        requirements_path="requirements.txt",
        artifact_paths=("requirements.txt", "backend/phase4.py"),
        enabled_features=frozenset({Phase4Feature.API_READS}),
    )
    return source, manifest


def test_assembly_copies_only_manifest_allowlist_and_validates(tmp_path):
    source, manifest = source_and_manifest(tmp_path)
    (source / "unlisted.txt").write_text("must not ship\n", encoding="utf-8")
    destination = tmp_path / "package"
    report = assemble_phase4_package(
        source,
        destination,
        serialize_build_manifest(manifest),
    )
    assert report == validate_phase4_package(destination)
    assert report.artifact_count == 2
    assert report.execution_authorized is False
    assert report.production_mutation_authorized is False
    assert report.deployment_authorized is False
    files = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file()
    }
    assert files == {
        "requirements.txt",
        "backend/phase4.py",
        PACKAGE_MANIFEST_FILENAME,
    }


def test_source_tamper_fails_before_destination_is_created(tmp_path):
    source, manifest = source_and_manifest(tmp_path)
    (source / "backend" / "phase4.py").write_text("SAFE = False\n", encoding="utf-8")
    destination = tmp_path / "package"
    with pytest.raises(PackageValidationError, match="integrity mismatch"):
        assemble_phase4_package(
            source,
            destination,
            serialize_build_manifest(manifest),
        )
    assert destination.exists() is False


def test_package_tamper_and_extra_file_are_rejected(tmp_path):
    source, manifest = source_and_manifest(tmp_path)
    first = tmp_path / "first"
    assemble_phase4_package(source, first, serialize_build_manifest(manifest))
    (first / "backend" / "phase4.py").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(PackageValidationError, match="integrity mismatch"):
        validate_phase4_package(first)

    second = tmp_path / "second"
    assemble_phase4_package(source, second, serialize_build_manifest(manifest))
    (second / "extra.txt").write_text("extra\n", encoding="utf-8")
    with pytest.raises(PackageValidationError, match="allowlist"):
        validate_phase4_package(second)


def test_existing_destination_is_never_overwritten(tmp_path):
    source, manifest = source_and_manifest(tmp_path)
    destination = tmp_path / "package"
    destination.mkdir()
    marker = destination / "user-data.txt"
    marker.write_text("preserve\n", encoding="utf-8")
    with pytest.raises(PackageValidationError, match="must not already exist"):
        assemble_phase4_package(
            source,
            destination,
            serialize_build_manifest(manifest),
        )
    assert marker.read_text(encoding="utf-8") == "preserve\n"


def test_prepare_and_verify_cli_round_trip_without_starting_runtime(tmp_path):
    source, manifest = source_and_manifest(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(serialize_build_manifest(manifest))
    destination = tmp_path / "package"
    repository_root = Path(__file__).parents[2]
    prepare = repository_root / "tools" / "prepare_phase4_package.py"
    verify = repository_root / "tools" / "verify_phase4_package.py"
    prepared = subprocess.run(
        [
            sys.executable,
            str(prepare),
            "--source-root",
            str(source),
            "--manifest",
            str(manifest_path),
            "--destination-root",
            str(destination),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=repository_root,
    )
    verified = subprocess.run(
        [sys.executable, str(verify), "--package-root", str(destination)],
        check=True,
        capture_output=True,
        text=True,
        cwd=repository_root,
    )
    assert prepared.stdout.startswith("PHASE4_PACKAGE_VALID")
    assert verified.stdout == prepared.stdout


def test_phase4_dockerfile_only_validates_and_exposes_no_service():
    repository_root = Path(__file__).parents[2]
    dockerfile = (
        repository_root / "deploy" / "phase4" / "Dockerfile"
    ).read_text(encoding="utf-8")
    assert "tools/verify_phase4_package.py" in dockerfile
    assert "USER arms" in dockerfile
    assert "ENTRYPOINT" in dockerfile
    assert "EXPOSE" not in dockerfile
    assert "backend.api" not in dockerfile
    assert "uvicorn" not in dockerfile
    assert "broker" not in dockerfile.lower()
