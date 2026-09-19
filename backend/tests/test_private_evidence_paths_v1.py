from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from backend.tests.private_evidence_paths_v1 import (
    private_runtime_manifest, resolve_evidence, resolve_from_environment,
)


@pytest.fixture
def evidence(tmp_path):
    source = tmp_path / "source.txt"
    source.write_bytes(b"20250619 150100;20000;20001;19999;20000;8\n")
    identity = "<ARMS_AI_SOURCE_EXPORT>/source.txt"
    value = {"segments": [{"source_file": identity,
                          "source_sha256": sha256(source.read_bytes()).hexdigest(),
                          "raw_row": "20250619 150100;20000;20001;19999;20000;8",
                          "contract": "JUN25", "count": 1}]}
    return source, identity, value


def test_resolves_only_paths_and_preserves_source_bytes_and_evidence(evidence):
    source, identity, value = evidence
    before = deepcopy(value)
    raw = source.read_bytes()
    resolved = resolve_evidence(value, {identity: str(source)})
    assert value == before and source.read_bytes() == raw
    assert resolved["segments"][0].pop("source_file") == str(source)
    expected = deepcopy(before["segments"][0])
    expected.pop("source_file")
    assert resolved["segments"][0] == expected


@pytest.mark.parametrize("failure", ["missing", "relative", "hash", "missing_digest", "unknown", "traversal"])
def test_invalid_private_resolution_fails_closed(evidence, failure):
    source, identity, value = evidence
    mapping = {identity: str(source)}
    if failure == "missing":
        mapping.clear()
    elif failure == "relative":
        mapping[identity] = "source.txt"
    elif failure == "hash":
        source.write_bytes(b"changed")
    elif failure == "missing_digest":
        value["segments"][0].pop("source_sha256")
    elif failure == "unknown":
        value["segments"][0]["source_file"] = "<UNKNOWN>/source.txt"
    else:
        value["segments"][0]["source_file"] = "<ARMS_AI_SOURCE_EXPORT>/../source.txt"
    with pytest.raises(ValueError):
        resolve_evidence(value, mapping)


def test_portable_input_requires_explicit_mapping_but_legacy_does_not(evidence, monkeypatch):
    _, _, value = evidence
    monkeypatch.delenv("ARMS_AI_PRIVATE_PATH_MAP", raising=False)
    with pytest.raises(ValueError, match="ARMS_AI_PRIVATE_PATH_MAP"):
        resolve_from_environment(value)
    legacy = {"source_file": "existing-relative-source.txt"}
    assert resolve_from_environment(legacy) is legacy


def test_runtime_manifest_is_private_reusable_and_does_not_change_canonical(evidence, tmp_path, monkeypatch):
    source, identity, value = evidence
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".arms-dev/\n")
    canonical = tmp_path / "canonical.json"
    canonical.write_text(json.dumps(value))
    original = canonical.read_bytes()
    mapping = tmp_path / ".arms-dev" / "map.json"
    mapping.parent.mkdir()
    mapping.write_text(json.dumps({"paths": {identity: str(source)}}))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ARMS_AI_PRIVATE_PATH_MAP", str(mapping))
    resolved = private_runtime_manifest(canonical)
    assert canonical.read_bytes() == original
    assert private_runtime_manifest(canonical) == resolved
    assert json.loads(resolved.read_text())["segments"][0]["source_file"] == str(source)
    assert subprocess.run(["git", "check-ignore", "--quiet", str(resolved)]).returncode == 0
    assert not subprocess.check_output(["git", "ls-files", str(resolved)])


def test_unignored_runtime_output_is_rejected(evidence, tmp_path, monkeypatch):
    source, identity, value = evidence
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    canonical = tmp_path / "canonical.json"
    canonical.write_text(json.dumps(value))
    mapping = tmp_path / "map.json"
    mapping.write_text(json.dumps({"paths": {identity: str(source)}}))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ARMS_AI_PRIVATE_PATH_MAP", str(mapping))
    with pytest.raises(ValueError, match="ignored"):
        private_runtime_manifest(canonical)
    assert not (tmp_path / ".arms-dev").exists()
