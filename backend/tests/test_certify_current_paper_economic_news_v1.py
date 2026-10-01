"""Explicit operator publication; no runtime source discovery."""
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

import pytest

from backend.services import current_paper_economic_news_authority_v1 as news
from backend.tests.test_current_paper_economic_news_authority_v1 import BASE, KEY, NOW, candidate
from tools import certify_current_paper_economic_news_v1 as publisher


def setup(tmp_path, monkeypatch):
    root = tmp_path / "current-paper"
    root.mkdir()
    monkeypatch.setattr(publisher, "read_bounded", lambda path: Path(path).read_bytes())
    monkeypatch.setattr(publisher, "private_path", lambda path: path)
    monkeypatch.setattr(news.key_store, "load_authority", lambda root: KEY)
    monkeypatch.setattr(news.key_store, "provision_authority", lambda root: sha256(KEY).hexdigest())
    monkeypatch.setattr(news.key_store, "_restrict_directory", lambda path: None)
    return root


def test_reviewed_publication_is_atomic_and_separate(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    first = candidate()
    path = tmp_path / "candidate.json"
    path.write_bytes(first)
    calls = []
    atomic = news.key_store._atomic
    def record(target, payload):
        calls.append(target.name)
        atomic(target,payload)
    monkeypatch.setattr(news.key_store, "_atomic", record)
    result = publisher.publish(path, sha256(first).hexdigest(), base=BASE, root=root,
        initialize_authority=True, initialize_history=True, clock=lambda: NOW)
    assert result["schema"] == news.SCHEMA
    assert calls == [news.FILES[2],news.FILES[0],news.FILES[1]]
    folder = root/"authority-inputs"
    assert not (folder/news.LOCK).exists()
    assert news.verify_history((folder/news.FILES[2]).read_bytes(),base=BASE,key=KEY)["entries"][-1]["sha256"] == sha256(first).hexdigest()
    assert "sim-native" not in str(root).lower()


def test_reviewed_input_uses_local_non_authority_path_contract(tmp_path, monkeypatch):
    path = tmp_path / "reviewed-input.json"
    path.write_bytes(b"reviewed")
    calls = []

    def safe_path(value, *, authority=False):
        calls.append((Path(value), authority))
        if authority:
            raise ValueError("repository path rejected as authority storage")
        return Path(value)

    monkeypatch.setattr(publisher.key_store, "safe_path", safe_path)
    assert publisher._read_reviewed_input(path) == b"reviewed"
    assert calls == [(path, False)]


@pytest.mark.parametrize("size,allowed", [(200_000, True), (200_001, False)])
def test_reviewed_input_is_bounded(tmp_path, size, allowed):
    path = tmp_path / "reviewed-input.json"
    path.write_bytes(b"x" * size)
    if allowed:
        assert len(publisher._read_reviewed_input(path)) == size
    else:
        with pytest.raises(ValueError, match="ARTIFACT_SIZE"):
            publisher._read_reviewed_input(path)


def test_reviewed_input_preserves_safe_path_redirection_gate(tmp_path, monkeypatch):
    path = tmp_path / "redirected.json"

    def reject(value, *, authority=False):
        assert Path(value) == path and authority is False
        raise ValueError("redirected path prohibited")

    monkeypatch.setattr(publisher.key_store, "safe_path", reject)
    with pytest.raises(ValueError, match="redirected path prohibited"):
        publisher._read_reviewed_input(path)


def test_publish_keeps_durable_authority_paths_private(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    path = tmp_path / "candidate.json"
    payload = candidate()
    path.write_bytes(payload)
    safe_calls = []
    private_reads = []

    def safe_path(value, *, authority=False):
        safe_calls.append((Path(value), authority))
        return Path(value)

    def private_read(value):
        checked = Path(value)
        private_reads.append(checked)
        return checked.read_bytes()

    monkeypatch.setattr(publisher.key_store, "safe_path", safe_path)
    monkeypatch.setattr(publisher, "read_bounded", private_read)
    publisher.publish(path, sha256(payload).hexdigest(), base=BASE, root=root,
        initialize_history=True, clock=lambda: NOW)
    folder = root / "authority-inputs"
    assert (path, False) in safe_calls
    assert (root, True) in safe_calls
    assert (folder, True) in safe_calls
    assert private_reads
    assert all(item.parent == folder and item.name in publisher.news.FILES
        for item in private_reads)
    assert path not in private_reads


def test_main_reads_identity_through_reviewed_input_contract(tmp_path, monkeypatch, capsys):
    identity = tmp_path / "identity.json"
    candidate_path = tmp_path / "candidate.json"
    identity_raw = publisher.canonical(BASE)
    identity.write_bytes(identity_raw)
    candidate_path.write_bytes(b"candidate")
    reads = []

    def reviewed_read(path):
        reads.append(Path(path))
        return Path(path).read_bytes()

    monkeypatch.setattr(publisher, "_read_reviewed_input", reviewed_read)
    monkeypatch.setattr(publisher, "publish", lambda *args, **kwargs: {"ok": True})
    publisher.main(["--candidate", str(candidate_path), "--candidate-sha256", "0" * 64,
        "--identity", str(identity), "--identity-sha256", sha256(identity_raw).hexdigest()])
    assert reads == [identity]
    assert capsys.readouterr().out.strip() == '{"ok": true}'


def test_sha_canonical_version_and_monotonic_gates(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    path = tmp_path/"candidate.json"
    first = candidate()
    path.write_bytes(first)
    with pytest.raises(ValueError, match="REVIEWED_DIGEST_MISMATCH"):
        publisher.publish(path,"0"*64,base=BASE,root=root,clock=lambda:NOW)
    path.write_bytes(b'{"version":1, "schema":"x"}')
    with pytest.raises(ValueError, match="CANDIDATE_NOT_CANONICAL"):
        publisher.publish(path,sha256(path.read_bytes()).hexdigest(),base=BASE,root=root,clock=lambda:NOW)
    path.write_bytes(first)
    publisher.publish(path,sha256(first).hexdigest(),base=BASE,root=root,
        initialize_history=True,clock=lambda:NOW)
    second = candidate(at=NOW+timedelta(seconds=1),snapshot_version="review.2")
    path.write_bytes(second)
    publisher.publish(path,sha256(second).hexdigest(),base=BASE,root=root,
        clock=lambda:NOW+timedelta(seconds=1))
    stale = candidate(at=NOW,snapshot_version="review.3")
    path.write_bytes(stale)
    with pytest.raises(ValueError,match="VERSION_ROLLBACK"):
        publisher.publish(path,sha256(stale).hexdigest(),base=BASE,root=root,
            clock=lambda:NOW+timedelta(seconds=1))
    assert (root/"authority-inputs"/news.LOCK).exists()


def test_duplicate_version_latches_publication_lock(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    path = tmp_path/"candidate.json"
    first = candidate()
    path.write_bytes(first)
    publisher.publish(path,sha256(first).hexdigest(),base=BASE,root=root,
        initialize_history=True,clock=lambda:NOW)
    with pytest.raises(ValueError,match="VERSION_REUSE"):
        publisher.publish(path,sha256(first).hexdigest(),base=BASE,root=root,clock=lambda:NOW)
    assert (root/"authority-inputs"/news.LOCK).exists()


def test_identity_and_candidate_cannot_claim_other_domain(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    path = tmp_path/"candidate.json"
    path.write_bytes(candidate())
    wrong = {**BASE,"execution_domain":"SIM_NATIVE"}
    with pytest.raises(ValueError,match="PAPER_BINDING_INVALID"):
        publisher.publish(path,sha256(path.read_bytes()).hexdigest(),base=wrong,root=root,
            initialize_history=True,clock=lambda:NOW)
    assert not (root/"authority-inputs").exists()
