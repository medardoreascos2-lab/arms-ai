"""Offline diagnostic-reader evidence; never a native capture."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tools import native_receipt_ledger_v1 as ledger

RUN = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
SESSION = 'bbbbbbbb-bbbb-4ccc-8ddd-eeeeeeeeeeee'


def raw(seq=0, kind='HELLO'):
    return ledger.canonical(dict(sequence=seq, session=SESSION, kind=kind, event_time='synthetic'))


def pair(q=10, f=10):
    return dict(qpc_before=q, qpc_after=q+1, frequency=f, host_unix_ns=0)


def test_sequential_exact_binding_and_duplicate_no_renewal(tmp_path):
    log = ledger.ReceiptLedger(tmp_path/'ledger', RUN, 10)
    one, two = raw(), raw(1, 'HEARTBEAT')
    original = log.observe(one, 0, len(one)+2, 10, 20)
    before = log.path.read_bytes()
    assert log.observe(one, 0, len(one)+2, 100, 200) == original
    assert log.path.read_bytes() == before
    log.observe(two, len(one)+2, len(two)+1, 30, 40)
    result = ledger.replay(log.path.read_bytes(), one+b'\r\n'+two+b'\n', b'', RUN, 10)
    assert result['records'] == 2 and result['runtime_admission'] is False
    assert result['ledger_sha256'] == ledger.digest(log.path.read_bytes())


@pytest.mark.parametrize('case', ['hash', 'offset', 'gap', 'regression', 'session'])
def test_conflicts_latch(tmp_path, case):
    log = ledger.ReceiptLedger(tmp_path/'ledger', RUN, 10)
    one = raw()
    log.observe(one, 0, len(one)+1, 10, 20)
    two, offset, before, after = raw(1), len(one)+1, 30, 40
    if case == 'hash': two, offset = raw(0, 'HEARTBEAT'), 0
    if case == 'offset': offset = 0
    if case == 'gap': two = raw(2)
    if case == 'regression': before, after = 1, 2
    if case == 'session': two = two.replace(SESSION.encode(), RUN.encode())
    with pytest.raises(ValueError): log.observe(two, offset, len(two)+1, before, after)
    with pytest.raises(ValueError, match='LEDGER_FAILED'): log.observe(one, 0, len(one)+1, 10, 20)


@pytest.mark.parametrize('case', ['frequency', 'offset', 'hash', 'sequence', 'encoding'])
def test_replay_tampering(tmp_path, case):
    log = ledger.ReceiptLedger(tmp_path/'ledger', RUN, 10)
    one = raw()
    log.observe(one, 0, len(one)+1, 10, 20)
    row = deepcopy(log.rows[0])
    key, value = {'frequency': ('qpc_frequency',11), 'offset': ('canonical_file_offset',1),
                  'hash': ('canonical_raw_sha256','0'*64), 'sequence': ('canonical_sequence',1),
                  'encoding': ('schema','wrong')}[case]
    row[key] = value
    with pytest.raises(ValueError):
        ledger.replay(ledger.canonical(row)+b'\n', one+b'\n', b'', RUN, 10)


def test_partial_read_retains_earliest_bracket(tmp_path):
    path = tmp_path/'native'
    values = iter([pair(q) for q in (10,20,30,40,50,60)])
    tail = ledger.StableFile(path, 10, sample=lambda: next(values))
    path.write_bytes(b'{"sequence":')
    assert tail.read() == []
    with path.open('ab') as f: f.write(b'0}\n')
    assert tail.read() == [(b'{"sequence":0}', 0, 15, 10, 41)]
    assert tail.read() == []


@pytest.mark.parametrize('case', ['truncate','replace','overwrite','qpc','frequency'])
def test_reader_integrity(tmp_path, case):
    path = tmp_path/'native'; path.write_bytes(b'one\n')
    values = iter([pair(10),pair(20),pair(1 if case=='qpc' else 30,11 if case=='frequency' else 10),pair(40)])
    tail = ledger.StableFile(path,10,sample=lambda: next(values))
    tail.read()
    if case == 'truncate': path.write_bytes(b'')
    if case == 'overwrite': path.write_bytes(b'two\n')
    if case == 'replace': path.rename(tmp_path/'old'); path.write_bytes(b'one\n')
    with pytest.raises(ValueError): tail.read()


def test_archive_all_records_replay_with_exact_timing_pairs(tmp_path):
    archive=json.loads((Path(__file__).parent/'production_timing_sprint15w.json').read_text())['native_capture']
    canonical=archive['native_canonical_utf8'].encode()
    timing=archive['native_timing_utf8'].encode()
    q=max(p['emission']['qpc_after'] for p in map(json.loads,timing.splitlines()))+10
    frequency=json.loads(timing.splitlines()[0])['qpc_frequency']
    log=ledger.ReceiptLedger(tmp_path/'ledger', RUN, frequency)
    offset=0
    for frame in canonical.splitlines(keepends=True):
        log.observe(frame.rstrip(b'\r\n'),offset,len(frame),q,q+1)
        offset+=len(frame)
    result=ledger.replay(log.path.read_bytes(),canonical,timing,RUN,frequency)
    assert len(result['bar_bindings'])==len(timing.splitlines())
    changed=timing.replace(b'"canonical_sha256":"',b'"canonical_sha256":"0',1)
    with pytest.raises(ValueError): ledger.replay(log.path.read_bytes(),canonical,changed,RUN,frequency)


def test_durable_flush_and_existing_file_refused(tmp_path, monkeypatch):
    calls=[]
    monkeypatch.setattr(ledger.os,'fsync',lambda fd:calls.append(fd))
    log=ledger.ReceiptLedger(tmp_path/'ledger',RUN,10)
    one=raw(); log.observe(one,0,len(one)+1,1,2)
    assert len(calls)==2
    with pytest.raises(FileExistsError): ledger.ReceiptLedger(log.path,RUN,10)
    log.path.write_bytes(b'tampered')
    with pytest.raises(ValueError): log.verify_disk()
