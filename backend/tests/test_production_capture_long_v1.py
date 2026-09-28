"""Offline tests for bounded long-capture storage.

No network, NinjaTrader process, account, order, command or activation is used.
"""

from contextlib import contextmanager
from pathlib import Path

import pytest

from tools import production_capture_long_v1 as longcap
from tools import production_timing_long_v1 as production
from tools.production_capture_profiles_v1 import profile
from backend.tests.test_native_receipt_ledger_v1 import RUN
from backend.tests.test_production_capture_contract_sprint15wr1 import recorded


def qpc_source(frequency=10_000_000, start=10):
    current = start

    def sample():
        nonlocal current
        value = current
        current += 10
        return {
            "frequency": frequency,
            "qpc_before": value,
            "qpc_after": value + 1,
            "host_unix_ns": 0,
        }

    return sample


def test_diskstream_incremental_append_and_final_verify(tmp_path):
    path = tmp_path / "stream.jsonl"
    path.write_bytes(b'{"n":1}\n')

    stream = longcap.DiskStream(
        path,
        "LONG_A",
        10_000_000,
        sample=qpc_source(),
    )

    rows = list(stream.poll())
    assert [row[0] for row in rows] == [b'{"n":1}']
    assert len(stream) == 1

    with path.open("ab") as handle:
        handle.write(b'{"n":2}\n')

    rows = list(stream.poll())
    assert [row[0] for row in rows] == [b'{"n":2}']
    assert len(stream) == 2

    stream.verify()


def test_diskstream_final_verify_detects_historical_prefix_mutation(tmp_path):
    path = tmp_path / "stream.jsonl"
    original = b'{"n":1}\n{"n":2}\n'
    path.write_bytes(original)

    stream = longcap.DiskStream(
        path,
        "LONG_A",
        10_000_000,
        sample=qpc_source(),
    )

    assert len(list(stream.poll())) == 2
    stream.verify()

    # Same length/inode, historical bytes changed.
    changed = bytearray(original)
    changed[5] = ord("9")
    path.write_bytes(bytes(changed))

    with pytest.raises(ValueError, match="PREFIX_MUTATION"):
        stream.verify()


def test_diskstream_long_profile_handles_over_256_records_and_2mb(tmp_path):
    path = tmp_path / "large.jsonl"

    # 300 records, each comfortably below the 64 KiB frame ceiling,
    # but total evidence > 2 MiB.
    payload = "x" * 7200
    with path.open("wb") as handle:
        for index in range(300):
            handle.write(
                (
                    '{"sequence":'
                    + str(index)
                    + ',"payload":"'
                    + payload
                    + '"}\n'
                ).encode()
            )

    assert path.stat().st_size > 2_000_000

    stream = longcap.DiskStream(
        path,
        "LONG_A",
        10_000_000,
        sample=qpc_source(),
    )

    rows = list(stream.poll())

    assert len(rows) == 300
    assert len(stream) == 300
    assert stream.size == path.stat().st_size

    stream.verify()


def test_journal_quick_verify_is_bounded_and_final_hash_detects_tamper(tmp_path):
    path = tmp_path / "journal.jsonl"

    journal = longcap.Journal(
        path,
        "LONG_A",
        kind="receipt",
    )

    journal.append({"sequence": 0, "value": "AAAA"})
    journal.append({"sequence": 1, "value": "BBBB"})

    journal.quick_verify()
    journal.verify()

    original = path.read_bytes()
    changed = original.replace(b"AAAA", b"ZZZZ")
    assert len(changed) == len(original)
    path.write_bytes(changed)

    # Live check intentionally checks identity/size only.
    journal.quick_verify()

    # Final immutable verification catches historical tampering.
    with pytest.raises(ValueError, match="JOURNAL_TAMPERED"):
        journal.verify()


def test_native_seal_is_plain_bounded_json_not_jsonl(tmp_path, monkeypatch):
    archive, proof = recorded()
    frequency = proof["qpc_frequency"]
    session = proof["session"]

    market = tmp_path / "market"
    timing_dir = market / "timing"
    receipts = tmp_path / "receipts"
    final = tmp_path / "final"

    timing_dir.mkdir(parents=True)
    receipts.mkdir()
    final.mkdir()

    canonical = archive["native_canonical_utf8"].encode()
    timing = archive["native_timing_utf8"].encode()
    seal = archive["native_seal_utf8"].encode()

    canonical_path = market / f"{session}.jsonl"
    timing_path = timing_dir / f"{session}.production-timing.jsonl"
    seal_path = Path(str(timing_path) + ".done.json")

    canonical_path.write_bytes(canonical)
    timing_path.write_bytes(timing)
    seal_path.write_bytes(seal)

    # Existing native seal is one JSON document and does not need newline framing.
    assert seal
    assert not seal.endswith(b"\n")

    @contextmanager
    def closed(_paths):
        yield True

    monkeypatch.setattr(longcap, "exclusive", closed)

    manifest = {
        "profile": profile("LONG_A").manifest(),
        "run_id": RUN,
        "qpc_frequency": frequency,
    }

    # Receipt QPC brackets must occur after the recorded native emissions.
    # This is synthetic offline timing only; it grants no runtime authority.
    receipt_start = proof["last_emission"]["qpc_after"] + 1000

    monitor = longcap.Monitor(
        tmp_path,
        manifest,
        sample=qpc_source(frequency, start=receipt_start),
    )

    sealed = monitor.poll()

    assert sealed is not None
    assert sealed.proof["status"] == "PASS"
    assert sealed.proof["closed"] == proof["closed"]
    assert seal_path not in monitor.streams

    sealed.verify()


def test_long_module_remains_non_authoritative():
    assert longcap.FLAGS == {
        "runtime_admission": False,
        "absolute_time_authority": "UNKNOWN",
        "data_freshness": "NOT_ASSERTED",
        "measurement_status": "MEASURED_NOT_ATTESTED",
    }


def test_diskstream_truncation_fails_closed(tmp_path):
    path = tmp_path / "truncate.jsonl"
    path.write_bytes(b'{"n":1}\n{"n":2}\n')

    stream = longcap.DiskStream(
        path,
        "LONG_A",
        10_000_000,
        sample=qpc_source(),
    )

    assert len(list(stream.poll())) == 2

    path.write_bytes(b'{"n":1}\n')

    with pytest.raises(ValueError, match="TRUNCATION_OR_BYTE_CEILING"):
        list(stream.poll())


def test_diskstream_replacement_fails_closed(tmp_path):
    path = tmp_path / "replace.jsonl"
    path.write_bytes(b'{"n":1}\n')

    stream = longcap.DiskStream(
        path,
        "LONG_A",
        10_000_000,
        sample=qpc_source(),
    )

    assert len(list(stream.poll())) == 1

    old = tmp_path / "old.jsonl"
    path.rename(old)
    path.write_bytes(b'{"n":1}\n')

    with pytest.raises(ValueError, match="FILE_REPLACED"):
        list(stream.poll())


def test_diskstream_record_ceiling_fails_closed(tmp_path):
    path = tmp_path / "records.jsonl"
    path.write_bytes(
        b'{"n":1}\n'
        b'{"n":2}\n'
        b'{"n":3}\n'
    )

    stream = longcap.DiskStream(
        path,
        "LONG_A",
        10_000_000,
        sample=qpc_source(),
        record_limit=2,
    )

    with pytest.raises(ValueError, match="RECORD_CEILING"):
        list(stream.poll())


def test_diskstream_byte_ceiling_fails_closed(tmp_path):
    path = tmp_path / "bytes.jsonl"
    path.write_bytes(b'{"payload":"abcdefghijklmnopqrstuvwxyz"}\n')

    stream = longcap.DiskStream(
        path,
        "LONG_A",
        10_000_000,
        sample=qpc_source(),
        byte_limit=16,
    )

    with pytest.raises(ValueError, match="TRUNCATION_OR_BYTE_CEILING"):
        list(stream.poll())


def test_diskstream_qpc_regression_fails_closed(tmp_path):
    path = tmp_path / "qpc.jsonl"
    path.write_bytes(b'{"n":1}\n')

    samples = iter([
        {
            "frequency": 10_000_000,
            "qpc_before": 100,
            "qpc_after": 101,
            "host_unix_ns": 0,
        },
        {
            "frequency": 10_000_000,
            "qpc_before": 90,
            "qpc_after": 91,
            "host_unix_ns": 0,
        },
    ])

    stream = longcap.DiskStream(
        path,
        "LONG_A",
        10_000_000,
        sample=lambda: next(samples),
    )

    with pytest.raises(ValueError, match="QPC_REGRESSION"):
        list(stream.poll())


def test_diskstream_frequency_change_fails_closed(tmp_path):
    path = tmp_path / "frequency.jsonl"
    path.write_bytes(b'{"n":1}\n')

    samples = iter([
        {
            "frequency": 10_000_000,
            "qpc_before": 100,
            "qpc_after": 101,
            "host_unix_ns": 0,
        },
        {
            "frequency": 9_999_999,
            "qpc_before": 102,
            "qpc_after": 103,
            "host_unix_ns": 0,
        },
    ])

    stream = longcap.DiskStream(
        path,
        "LONG_A",
        10_000_000,
        sample=lambda: next(samples),
    )

    with pytest.raises(ValueError, match="QPC_FREQUENCY_CHANGED"):
        list(stream.poll())







































def test_diskstream_partial_frame_retains_earliest_qpc_bracket(tmp_path):
    path = tmp_path / "partial.jsonl"

    # First physical read sees only the beginning of one frame.
    path.write_bytes(b'{"n":')

    stream = longcap.DiskStream(
        path,
        "LONG_A",
        10_000_000,
        sample=qpc_source(),
    )

    assert list(stream.poll()) == []
    assert stream.partial == b'{"n":'

    # Complete the same frame during a later poll.
    with path.open("ab") as handle:
        handle.write(b'1}\n')

    rows = list(stream.poll())

    assert len(rows) == 1

    raw, offset, frame_bytes, qpc_before, qpc_after = rows[0]

    assert raw == b'{"n":1}'
    assert offset == 0
    assert frame_bytes == len(b'{"n":1}\n')

    # qpc_source(): first read begins at 10, second read ends at 41.
    # The split frame must retain the earliest bracket, not renew it.
    assert qpc_before == 10
    assert qpc_after == 41


def test_diskstream_live_poll_does_not_full_hash_history(tmp_path, monkeypatch):
    path = tmp_path / "incremental.jsonl"
    path.write_bytes(b'{"n":1}\n')

    stream = longcap.DiskStream(
        path,
        "LONG_A",
        10_000_000,
        sample=qpc_source(),
    )

    def forbidden_full_hash(*args, **kwargs):
        raise AssertionError("LIVE_FULL_HASH_CALLED")

    # A live poll must use identity/size + incremental bytes only.
    monkeypatch.setattr(longcap, "file_hash", forbidden_full_hash)

    assert len(list(stream.poll())) == 1

    with path.open("ab") as handle:
        handle.write(b'{"n":2}\n')

    assert len(list(stream.poll())) == 1
    assert len(stream) == 2


def test_journal_quick_verify_does_not_hash_but_final_verify_does(
    tmp_path, monkeypatch
):
    path = tmp_path / "quick-journal.jsonl"

    journal = longcap.Journal(
        path,
        "LONG_A",
        kind="receipt",
    )

    journal.append({"sequence": 0, "value": "test"})

    def forbidden_full_hash(*args, **kwargs):
        raise AssertionError("FULL_HASH_CALLED")

    monkeypatch.setattr(longcap, "file_hash", forbidden_full_hash)

    # Repeated live validation must remain metadata-only.
    journal.quick_verify()

    # Final verification intentionally performs the complete hash.
    with pytest.raises(AssertionError, match="FULL_HASH_CALLED"):
        journal.verify()


def test_sealed_quick_verify_does_not_rehash_but_final_verify_does(
    tmp_path, monkeypatch
):
    path = tmp_path / "sealed.json"
    path.write_bytes(b'{"sealed":true}')

    class DummyMonitor:
        def __init__(self):
            self.p = profile("LONG_A")
            self.actual = {path}

        def inventory(self):
            # Structural inventory only for this isolated offline test.
            assert path.exists()

    monitor = DummyMonitor()

    # Constructor establishes the immutable full-hash signature once.
    sealed = longcap.SealedCapture(
        monitor,
        {"status": "PASS"},
    )

    def forbidden_full_hash(*args, **kwargs):
        raise AssertionError("SEALED_FULL_HASH_CALLED")

    monkeypatch.setattr(longcap, "file_hash", forbidden_full_hash)

    # Repeated post-closure checks must not rehash historical bytes.
    sealed.quick_verify()

    # Final immutable verification must still perform the full hash.
    with pytest.raises(AssertionError, match="SEALED_FULL_HASH_CALLED"):
        sealed.verify()



def test_journal_short_write_fails_closed_and_latches(tmp_path, monkeypatch):
    path = tmp_path / "short-write.jsonl"

    journal = longcap.Journal(
        path,
        "LONG_A",
        kind="receipt",
    )

    real_local = longcap.local

    class ShortWriteHandle:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            self.handle.__enter__()
            return self

        def __exit__(self, *args):
            return self.handle.__exit__(*args)

        def fileno(self):
            return self.handle.fileno()

        def write(self, raw):
            # Simulate an OS/filesystem short write without changing production code.
            return max(0, len(raw) - 1)

    class ShortWritePath:
        def __init__(self, actual):
            self.actual = actual

        def open(self, *args, **kwargs):
            return ShortWriteHandle(
                self.actual.open(*args, **kwargs)
            )

    def patched_local(value):
        actual = real_local(value)
        if actual == path:
            return ShortWritePath(actual)
        return actual

    monkeypatch.setattr(longcap, "local", patched_local)

    with pytest.raises(ValueError, match="SHORT_WRITE"):
        journal.append({"sequence": 0, "value": "short"})

    assert journal.failed is True

    # Once a durable-write failure occurs, the journal must remain failed.
    with pytest.raises(ValueError, match="JOURNAL_FAILED"):
        journal.append({"sequence": 0, "value": "retry"})


def test_journal_external_growth_fails_closed(tmp_path):
    path = tmp_path / "external-growth.jsonl"

    journal = longcap.Journal(
        path,
        "LONG_A",
        kind="receipt",
    )

    journal.append({"sequence": 0, "value": "one"})

    # Simulate an unauthorized writer appending behind the owner's back.
    with path.open("ab") as handle:
        handle.write(b'{"foreign":true}\n')

    with pytest.raises(ValueError, match="JOURNAL_CHANGED"):
        journal.append({"sequence": 1, "value": "two"})

    assert journal.failed is True


def test_journal_replacement_fails_quick_verify(tmp_path):
    path = tmp_path / "replace-journal.jsonl"

    journal = longcap.Journal(
        path,
        "LONG_A",
        kind="receipt",
    )

    journal.append({"sequence": 0, "value": "one"})

    old = tmp_path / "old-journal.jsonl"
    path.rename(old)
    path.write_bytes(old.read_bytes())

    with pytest.raises(ValueError, match="JOURNAL_CHANGED"):
        journal.quick_verify()


def test_read_journal_rejects_truncated_final_frame(tmp_path):
    path = tmp_path / "truncated-journal.jsonl"

    journal = longcap.Journal(
        path,
        "LONG_A",
        kind="receipt",
    )

    journal.append({"sequence": 0, "value": "complete"})

    raw = path.read_bytes()
    assert raw.endswith(b"\n")

    # Remove only the JSONL terminator.
    path.write_bytes(raw[:-1])

    p = profile("LONG_A")

    with pytest.raises(
        ValueError,
        match="JOURNAL_CEILING_OR_TRUNCATION",
    ):
        list(
            longcap.read_journal(
                path,
                "LONG_A",
                p.maximum_receipt_bytes,
                p.maximum_receipt_records,
            )
        )



def replay_fixture(tmp_path):
    p = profile("LONG_A")

    manifest = {
        "profile": p.manifest(),
        "run_id": RUN,
        "qpc_frequency": 10_000_000,
    }

    artifacts = {
        "synthetic": {
            "bytes": 1,
            "sha256": "0" * 64,
        },
        "clock/windows-before.json": {
            "bytes": 1,
            "sha256": "1" * 64,
        },
        "clock/windows-after.json": {
            "bytes": 1,
            "sha256": "2" * 64,
        },
    }

    final = {
        "result": "INCONCLUSIVE",
        "structural_result": "STRUCTURAL_PASS",
        "reason": None,
        "profile_id": p.profile_id,
        "run_id": RUN,
        **longcap.FLAGS,
        "configuration": manifest,
        "artifacts": artifacts,
    }

    (tmp_path / "final").mkdir(parents=True, exist_ok=True)

    return p, manifest, artifacts, final


def install_replay_base(monkeypatch, tmp_path, manifest, artifacts):
    monkeypatch.setattr(
        longcap,
        "load_run",
        lambda _folder: (tmp_path, manifest),
    )

    monkeypatch.setattr(
        longcap,
        "inventory",
        lambda _folder, _profile: artifacts,
    )


def test_replay_rejects_non_structural_pass_manifest(tmp_path, monkeypatch):
    _p, manifest, artifacts, final = replay_fixture(tmp_path)

    install_replay_base(
        monkeypatch,
        tmp_path,
        manifest,
        artifacts,
    )

    # Old/incorrect vocabulary must never be accepted as a completed LONG run.
    final["structural_result"] = "PASS"

    longcap.short.write_json(
        tmp_path / "final" / "capture-manifest.json",
        final,
    )

    with pytest.raises(
        ValueError,
        match="FINAL_PROFILE_COMPLETION",
    ):
        longcap.replay(tmp_path)


def test_replay_rejects_incomplete_coordinator(tmp_path, monkeypatch):
    _p, manifest, artifacts, final = replay_fixture(tmp_path)

    install_replay_base(
        monkeypatch,
        tmp_path,
        manifest,
        artifacts,
    )

    longcap.short.write_json(
        tmp_path / "final" / "capture-manifest.json",
        final,
    )

    # Even with a valid final manifest, pending closure is not COMPLETE.
    coordinator = {
        "snapshot": {
            "state": "COMPLETE",
            "reason": None,
            "run_id": RUN,
            "runtime_admission": False,
            "pending_closure": True,
            "collector_must_continue": False,
        },
        "events": [],
    }

    longcap.short.write_json(
        tmp_path / "final" / "coordinator.json",
        coordinator,
    )

    with pytest.raises(
        ValueError,
        match="COORDINATOR_NOT_COMPLETE",
    ):
        longcap.replay(tmp_path)


def test_replay_rejects_long_capture_below_profile_closed_minimum(
    tmp_path, monkeypatch
):
    p, manifest, artifacts, final = replay_fixture(tmp_path)

    install_replay_base(
        monkeypatch,
        tmp_path,
        manifest,
        artifacts,
    )

    longcap.short.write_json(
        tmp_path / "final" / "capture-manifest.json",
        final,
    )

    coordinator = {
        "snapshot": {
            "state": "COMPLETE",
            "reason": None,
            "run_id": RUN,
            "runtime_admission": False,
            "pending_closure": False,
            "collector_must_continue": False,
        },
        "events": [],
    }

    longcap.short.write_json(
        tmp_path / "final" / "coordinator.json",
        coordinator,
    )

    archive, recorded_proof = recorded()
    session = recorded_proof["session"]

    market = tmp_path / "market"
    timing_dir = market / "timing"
    timing_dir.mkdir(parents=True)

    native_path = market / f"{session}.jsonl"
    timing_path = (
        timing_dir
        / f"{session}.production-timing.jsonl"
    )
    seal_path = Path(str(timing_path) + ".done.json")

    native_path.write_bytes(
        archive["native_canonical_utf8"].encode()
    )
    timing_path.write_bytes(
        archive["native_timing_utf8"].encode()
    )
    seal_path.write_bytes(
        archive["native_seal_utf8"].encode()
    )

    # Window replay is not the subject of this isolated gate test.
    monkeypatch.setattr(
        longcap,
        "read_journal",
        lambda *args, **kwargs: iter(()),
    )

    # Simulate an otherwise structurally valid production proof
    # that contains fewer CLOSED bars than LONG_A requires.
    monkeypatch.setattr(
        longcap.production,
        "adjudicate",
        lambda *args, **kwargs: {
            "status": "PASS",
            "closed": p.minimum_closed - 1,
        },
    )

    with pytest.raises(
        ValueError,
        match="PRODUCTION_REPLAY",
    ):
        longcap.replay(tmp_path)



@pytest.mark.parametrize(
    "missing",
    [
        "clock/windows-before.json",
        "clock/windows-after.json",
    ],
)
def test_replay_requires_windows_time_evidence(
    tmp_path,
    monkeypatch,
    missing,
):
    _p, manifest, artifacts, final = replay_fixture(tmp_path)

    # Remove exactly one required descriptive Windows Time snapshot.
    artifacts.pop(missing)

    install_replay_base(
        monkeypatch,
        tmp_path,
        manifest,
        artifacts,
    )

    longcap.short.write_json(
        tmp_path / "final" / "capture-manifest.json",
        final,
    )

    with pytest.raises(
        ValueError,
        match="WINDOWS_TIME_EVIDENCE_MISSING",
    ):
        longcap.replay(tmp_path)
