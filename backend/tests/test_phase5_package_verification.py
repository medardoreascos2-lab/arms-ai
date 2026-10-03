"""R57C staging package reconstruction and hash verification tests."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from backend.phase5.package_verification import (
    StagingPackageVerificationError,
    verify_reconstructable_staging_package,
)


GIT_SHA = "9" * 40


def _make_writable(root: Path) -> None:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o666)


def _source(root: Path) -> Path:
    root.mkdir()
    (root / "requirements.txt").write_text("fastapi==0.139.2\n", encoding="utf-8")
    for phase in ("phase3", "phase4", "phase5"):
        path = root / "backend" / phase / "runtime.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'PHASE = "{phase}"\n', encoding="utf-8")
    return root


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _build(source: Path, package: Path, repository_root: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(repository_root / "tools" / "build_phase5_staging_package.py"),
            "--repository-root",
            str(source),
            "--destination-root",
            str(package),
            "--git-sha",
            GIT_SHA,
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=repository_root,
    )


def test_package_is_reconstructed_and_hash_checked_without_deployment(tmp_path):
    repository_root = Path(__file__).parents[2]
    package = tmp_path / "package"
    reconstruction = tmp_path / "reconstruction"
    _build(_source(tmp_path / "source"), package, repository_root)

    try:
        report = verify_reconstructable_staging_package(
            package.resolve(), reconstruction.resolve()
        )
        cli_reconstruction = tmp_path / "cli-reconstruction"
        cli = subprocess.run(
            [
                sys.executable,
                str(repository_root / "tools" / "verify_phase5_staging_package.py"),
                "--package-root",
                str(package),
                "--reconstruction-root",
                str(cli_reconstruction),
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=repository_root,
        )

        assert _files(package) == _files(reconstruction) == _files(cli_reconstruction)
        assert len(report.manifest_sha256) == 64
        assert len(report.package_sha256) == 64
        assert report.artifact_count == 4
        assert report.reconstructed is True
        assert report.execution_authorized is False
        assert report.production_mutation_authorized is False
        assert report.deployment_authorized is False
        assert cli.stdout.startswith("PHASE5_PACKAGE_VERIFICATION_PASS")
        assert "deployment_authorized=false" in cli.stdout
    finally:
        _make_writable(package)
        _make_writable(reconstruction)
        _make_writable(tmp_path / "cli-reconstruction")


def test_tampered_package_is_rejected_before_reconstruction(tmp_path):
    repository_root = Path(__file__).parents[2]
    package = tmp_path / "package"
    reconstruction = tmp_path / "reconstruction"
    _build(_source(tmp_path / "source"), package, repository_root)
    artifact = package / "backend" / "phase5" / "runtime.py"

    try:
        os.chmod(artifact, 0o666)
        artifact.write_text('PHASE = "tampered"\n', encoding="utf-8")
        with pytest.raises(
            StagingPackageVerificationError,
            match="reconstruction failed",
        ):
            verify_reconstructable_staging_package(
                package.resolve(), reconstruction.resolve()
            )
        assert reconstruction.exists() is False
    finally:
        _make_writable(package)


def test_verification_tool_has_no_deployment_or_runtime_authority():
    repository_root = Path(__file__).parents[2]
    source = (
        repository_root / "tools" / "verify_phase5_staging_package.py"
    ).read_text(encoding="utf-8").lower()
    forbidden = (
        "docker push",
        "podman push",
        "kubectl",
        "helm",
        "uvicorn.run",
        "subprocess.popen",
        "broker_connector",
        "enterlong",
        "entershort",
    )
    assert all(token not in source for token in forbidden)
