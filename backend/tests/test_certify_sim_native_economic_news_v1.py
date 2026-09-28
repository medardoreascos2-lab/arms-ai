"""Explicit publisher tests use isolated synthetic inputs and keys only."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest

from backend.services import sim_native_economic_news_authority_v1 as m
from backend.services import sim_native_authority_v3 as auth
from backend.services.sim_native_market_hours_authority_v1 import PINS, POLICY
from backend.tests.test_sim_native_economic_news_authority_v1 import document, KEY, disk
from tools import certify_sim_native_economic_news_v1 as tool


@pytest.fixture
def issuer(tmp_path,monkeypatch):
    config={**PINS,'authority_id':auth.authority_id(KEY),'configuration_generation':'3'}
    monkeypatch.setattr(auth,'authority_root',lambda:tmp_path)
    monkeypatch.setattr(auth,'safe_path',lambda p,**kw:Path(p))
    monkeypatch.setattr(auth,'_restrict_directory',lambda p:None)
    monkeypatch.setattr(m,'read_bounded',lambda p:Path(p).read_bytes())
    monkeypatch.setattr(tool,'private_path',lambda p:Path(p))
    monkeypatch.setattr(tool,'production_context',lambda:(config,POLICY,KEY))
    return tmp_path,config,document(config,KEY,datetime.now(timezone.utc))


def publish(issuer,value,**kw):
    root,_,_=issuer
    source=root/'reviewed-candidate.json';source.write_bytes(m.canonical(value))
    return tool.publish(source,hashlib.sha256(source.read_bytes()).hexdigest(),**kw)


def test_explicit_first_publication_and_monotonic_replacement(issuer):
    root,config,v=issuer
    original=deepcopy(v)
    result=publish(issuer,v,initialize_history=True)
    assert result['news_policy_id']==m.NEWS_POLICY_ID and original==v
    assert not (root/'authority-inputs'/m.LOCK).exists()
    v.update(snapshot_version='synthetic-2',issued_us=v['issued_us']+1)
    publish(issuer,v)
    history=m.verify_history((root/'authority-inputs'/m.FILES[2]).read_bytes(),config=config,policy_id=POLICY,key=KEY)
    assert [e['snapshot_version'] for e in history['entries']]==['synthetic-1','synthetic-2']
    assert history['entries'][-1]['sha256']==hashlib.sha256(m.canonical(v)).hexdigest()


@pytest.mark.parametrize('damage',['rollback','conflict','reuse','missing_history','reinitialize','hmac'])
def test_failed_reissue_preserves_package_and_leaves_fail_closed_lock(issuer,damage):
    root,_,v=issuer;publish(issuer,v,initialize_history=True)
    folder=root/'authority-inputs';before=(folder/m.FILES[0]).read_bytes()
    if damage=='rollback':v.update(snapshot_version='older',issued_us=v['issued_us']-1,generated_us=v['generated_us']-1)
    elif damage=='conflict':v['source_sha256']='b'*64
    elif damage=='missing_history':(folder/m.FILES[2]).unlink()
    elif damage=='hmac':(folder/m.FILES[2]).write_bytes(b'{}')
    with pytest.raises(ValueError):publish(issuer,v,initialize_history=damage=='reinitialize')
    assert (folder/m.FILES[0]).read_bytes()==before
    assert (folder/m.LOCK).exists()


def test_unreviewed_digest_cannot_publish(issuer):
    root,_,v=issuer;p=root/'candidate.json';p.write_bytes(m.canonical(v))
    before=disk(root)
    with pytest.raises(ValueError,match='DIGEST'):tool.publish(p,'0'*64,initialize_history=True)
    assert disk(root)==before


def test_missing_initial_history_never_silently_initializes(issuer):
    with pytest.raises(ValueError,match='HISTORY_REQUIRED'):publish(issuer,issuer[2])


def test_torn_publication_floor_advances_before_active_package(issuer,monkeypatch):
    root,_,v=issuer;publish(issuer,v,initialize_history=True)
    folder=root/'authority-inputs';old=(folder/m.FILES[0]).read_bytes()
    v.update(snapshot_version='synthetic-2',issued_us=v['issued_us']+1)
    atomic=auth._atomic
    def fail(path,data,**kw):
        if path.name==m.FILES[0]:raise OSError('synthetic disk failure')
        return atomic(path,data,**kw)
    monkeypatch.setattr(auth,'_atomic',fail)
    with pytest.raises(OSError):publish(issuer,v)
    assert (folder/m.LOCK).exists() and (folder/m.FILES[0]).read_bytes()==old
    assert b'synthetic-2' in (folder/m.FILES[2]).read_bytes()
