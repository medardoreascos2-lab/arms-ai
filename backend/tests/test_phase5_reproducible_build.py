"""R57A deterministic local Phase 5 staging package tests."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys

from backend.phase3.durable_store import STORE_SCHEMA_VERSION
from backend.phase4.build_manifest import deserialize_build_manifest
from backend.phase4.package_validation import (
    PACKAGE_MANIFEST_FILENAME,
    validate_phase4_package,
)
from backend.phase4.production_migrations import POSTGRES_SCHEMA_VERSION
from backend.phase4.staging_runtime import REQUIRED_STAGING_FEATURES


GIT_SHA = "5" * 40


def _source(root: Path):
    root.mkdir()
    (root / "requirements.txt").write_text(
        "uvicorn==0.51.0\nfastapi==0.139.2\n",
        encoding="utf-8",
    )
    contents = {
        "backend/phase3/runtime.py": "PHASE = 3\n",
        "backend/phase4/runtime.py": "PHASE = 4\n",
        "backend/phase5/runtime.py": "PHASE = 5\n",
    }
    for relative, content in contents.items():
        path = root.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (root / "unlisted.txt").write_text("must-not-ship\n", encoding="utf-8")
    return root


def _package_files(root: Path):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _make_writable(root: Path):
    for path in root.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o666)


def test_two_staging_builds_are_identical_and_record_complete_provenance(tmp_path):
    source = _source(tmp_path / "source")
    first = tmp_path / "package-a"
    second = tmp_path / "package-b"
    repository_root = Path(__file__).parents[2]
    script = repository_root / "tools" / "build_phase5_staging_package.py"
    outputs = []

    for destination in (first, second):
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--repository-root",
                str(source),
                "--destination-root",
                str(destination),
                "--git-sha",
                GIT_SHA,
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=repository_root,
        )
        outputs.append(result.stdout)

    try:
        first_files = _package_files(first)
        second_files = _package_files(second)
        manifest = deserialize_build_manifest(first_files[PACKAGE_MANIFEST_FILENAME])

        assert first_files == second_files
        assert outputs[0] == outputs[1]
        assert outputs[0].startswith("PHASE5_STAGING_PACKAGE_VALID")
        assert "deployment_authorized=false" in outputs[0]
        assert validate_phase4_package(first) == validate_phase4_package(second)
        assert manifest.source_git_sha == GIT_SHA
        assert manifest.phase3_schema_version == STORE_SCHEMA_VERSION
        assert manifest.phase4_migration_version == POSTGRES_SCHEMA_VERSION
        assert tuple((item.name, item.version) for item in manifest.dependency_versions) == (
            ("fastapi", "0.139.2"),
            ("uvicorn", "0.51.0"),
        )
        assert manifest.feature_flags == tuple(
            sorted(feature.value for feature in REQUIRED_STAGING_FEATURES)
        )
        assert tuple(item.path for item in manifest.artifacts) == (
            "backend/phase3/runtime.py",
            "backend/phase4/runtime.py",
            "backend/phase5/runtime.py",
            "requirements.txt",
        )
        assert {
            item.path: item.sha256 for item in manifest.artifacts
        } == {
            path: hashlib.sha256(payload).hexdigest()
            for path, payload in first_files.items()
            if path != PACKAGE_MANIFEST_FILENAME
        }
        assert "unlisted.txt" not in first_files
        assert manifest.execution_authorized is False
        assert manifest.production_mutation_authorized is False
        assert manifest.deployment_authorized is False
    finally:
        _make_writable(first)
        _make_writable(second)


def test_staging_build_tool_has_no_image_push_or_runtime_start_authority():
    repository_root = Path(__file__).parents[2]
    source = (
        repository_root / "tools" / "build_phase5_staging_package.py"
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
