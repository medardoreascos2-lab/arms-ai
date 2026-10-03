"""R46B tests for deterministic build provenance."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from backend.phase3.durable_store import STORE_SCHEMA_VERSION
from backend.phase4.build_manifest import (
    BUILD_MANIFEST_FORMAT,
    BuildManifestError,
    deserialize_build_manifest,
    generate_build_manifest,
    parse_dependency_versions,
    serialize_build_manifest,
)
from backend.phase4.deployment_config import Phase4Feature
from backend.phase4.production_migrations import POSTGRES_SCHEMA_VERSION


GIT_SHA = "1" * 40
FEATURES = frozenset({Phase4Feature.METRICS_EXPORT, Phase4Feature.API_READS})


def repository(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "requirements.txt").write_text(
        "uvicorn==0.51.0\nfastapi==0.139.2\n",
        encoding="utf-8",
    )
    (root / "app.py").write_text("print('phase4')\n", encoding="utf-8")
    (root / "config.json").write_text('{"safe":true}\n', encoding="utf-8")
    return root


def build(root: Path, artifacts=("app.py", "config.json")):
    return generate_build_manifest(
        root,
        source_git_sha=GIT_SHA,
        requirements_path="requirements.txt",
        artifact_paths=tuple(artifacts),
        enabled_features=FEATURES,
    )


def test_manifest_is_canonical_deterministic_and_complete(tmp_path):
    root = repository(tmp_path / "source")
    first = build(root, ("config.json", "app.py"))
    second = build(root, ("app.py", "config.json"))
    assert serialize_build_manifest(first) == serialize_build_manifest(second)
    assert deserialize_build_manifest(serialize_build_manifest(first)) == first
    assert first.format == BUILD_MANIFEST_FORMAT
    assert first.source_git_sha == GIT_SHA
    assert first.phase3_schema_version == STORE_SCHEMA_VERSION
    assert first.phase4_migration_version == POSTGRES_SCHEMA_VERSION
    assert tuple(item.name for item in first.dependency_versions) == (
        "fastapi",
        "uvicorn",
    )
    assert first.feature_flags == ("api_reads", "metrics_export")
    assert tuple(item.path for item in first.artifacts) == ("app.py", "config.json")
    assert first.execution_authorized is False
    assert first.production_mutation_authorized is False
    assert first.deployment_authorized is False


def test_artifact_content_change_changes_hash_and_manifest_digest(tmp_path):
    root = repository(tmp_path / "source")
    first = build(root)
    (root / "app.py").write_text("print('changed')\n", encoding="utf-8")
    second = build(root)
    assert first.artifacts[0].sha256 != second.artifacts[0].sha256
    assert first.manifest_sha256 != second.manifest_sha256


def test_tampered_or_noncanonical_manifest_is_rejected(tmp_path):
    manifest = build(repository(tmp_path / "source"))
    raw = json.loads(serialize_build_manifest(manifest))
    raw["artifacts"][0]["size_bytes"] += 1
    tampered = (json.dumps(raw, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with pytest.raises(BuildManifestError, match="checksum mismatch"):
        deserialize_build_manifest(tampered)
    pretty = json.dumps(json.loads(serialize_build_manifest(manifest)), indent=2).encode()
    with pytest.raises(BuildManifestError, match="not canonical"):
        deserialize_build_manifest(pretty)


@pytest.mark.parametrize(
    "content",
    (
        "fastapi>=0.139.2\n",
        "fastapi\n",
        "fastapi==0.139.2\nFASTAPI==0.139.2\n",
    ),
)
def test_dependencies_must_be_exact_and_unique(content):
    with pytest.raises(BuildManifestError):
        parse_dependency_versions(content)


@pytest.mark.parametrize(
    "artifact",
    ("../outside.txt", "/absolute.txt", ".env", "private.pem", "folder\\file"),
)
def test_artifact_paths_reject_escape_and_sensitive_files(tmp_path, artifact):
    root = repository(tmp_path / "source")
    with pytest.raises(BuildManifestError):
        build(root, (artifact,))


def test_missing_and_duplicate_artifacts_fail_closed(tmp_path):
    root = repository(tmp_path / "source")
    with pytest.raises(BuildManifestError):
        build(root, ("missing.txt",))
    with pytest.raises(BuildManifestError, match="unique"):
        build(root, ("app.py", "app.py"))


def test_cli_generates_same_valid_manifest_without_deploying(tmp_path):
    root = repository(tmp_path / "source")
    output = tmp_path / "output" / "build-manifest.json"
    repository_root = Path(__file__).parents[2]
    script = repository_root / "tools" / "generate_phase4_build_manifest.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--repository-root",
            str(root),
            "--output",
            str(output),
            "--git-sha",
            GIT_SHA,
            "--artifact",
            "app.py",
            "--artifact",
            "config.json",
            "--feature",
            "metrics_export",
            "--feature",
            "api_reads",
        ],
        check=True,
        cwd=repository_root,
    )
    generated = deserialize_build_manifest(output.read_bytes())
    assert serialize_build_manifest(generated) == serialize_build_manifest(build(root))


def test_cli_uses_head_only_for_a_clean_git_worktree(tmp_path):
    root = repository(tmp_path / "source")
    for command in (
        ("init", "-q"),
        ("config", "user.email", "phase4@example.invalid"),
        ("config", "user.name", "Phase4 Test"),
        ("add", "requirements.txt", "app.py", "config.json"),
        ("commit", "-q", "-m", "fixture"),
    ):
        subprocess.run(["git", "-C", str(root), *command], check=True)
    repository_root = Path(__file__).parents[2]
    script = repository_root / "tools" / "generate_phase4_build_manifest.py"
    base_command = [
        sys.executable,
        str(script),
        "--repository-root",
        str(root),
        "--artifact",
        "app.py",
    ]
    clean_output = tmp_path / "clean.json"
    subprocess.run(
        [*base_command, "--output", str(clean_output)],
        check=True,
        cwd=repository_root,
    )
    assert deserialize_build_manifest(clean_output.read_bytes()).source_git_sha == (
        subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )

    (root / "app.py").write_text("dirty\n", encoding="utf-8")
    dirty_output = tmp_path / "dirty.json"
    rejected = subprocess.run(
        [*base_command, "--output", str(dirty_output)],
        cwd=repository_root,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode != 0
    assert "clean Git worktree" in rejected.stderr
    assert dirty_output.exists() is False
