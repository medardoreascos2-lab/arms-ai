"""Synthetic multi-factor proof contracts; no Account.All or native adapter."""
from datetime import datetime, timedelta, timezone
from dataclasses import asdict, replace

import pytest

from backend.market_data.sim_binding_contract_v1 import PrivateBindingV1, assess_sim_binding, OfflineBindingLatchV1
from backend.tests.test_current_paper_sprint10 import service, api_settings


def fixture():
    binding=PrivateBindingV1('synthetic-account-A','synthetic-connection-A','Simulator',
        'synthetic-label-digest','synthetic-installation','SYNTHETIC_PLATFORM_CLASS_V1',True)
    now=datetime(2026,9,22,tzinfo=timezone.utc)
    snapshot={**asdict(binding),'classification':'PROVEN_SIMULATION','account_count':1,
        'configuration_sha256':binding.digest(),'observed_at':now.isoformat(),'revoked':False}
    return binding,now,snapshot


@pytest.mark.parametrize('case', ['proven_sim','proven_real','unknown','missing','provider','connection',
    'renamed','name_sim','provider_only','allowlist_mismatch','config','account_changed','multiple','none','stale','future','revoked','disabled','wildcard','installation'])
def test_binding_matrix_and_no_order_authority(case):
    binding,now,snapshot=fixture()
    if case=='proven_real': snapshot['classification']='PROVEN_NON_SIMULATION'
    if case=='unknown': snapshot['classification']='UNKNOWN'
    if case=='missing': snapshot.pop('proof_contract')
    if case=='provider': snapshot['provider']='Provider31'
    if case=='connection': snapshot['connection_ref']='synthetic-other'
    if case=='renamed': snapshot['label_digest']='synthetic-new-label'
    if case=='name_sim': snapshot.update(classification='Sim101',proof_contract='NAME_ONLY')
    if case=='provider_only': snapshot['proof_contract']='PROVIDER_ENUM_ONLY'
    if case in {'allowlist_mismatch','account_changed'}: snapshot['account_ref']='synthetic-other'
    if case=='config': snapshot['configuration_sha256']='0'*64
    if case=='multiple': snapshot['account_count']=2
    if case=='none': snapshot['account_count']=0
    if case=='stale': snapshot['observed_at']=(now-timedelta(seconds=16)).isoformat()
    if case=='future': snapshot['observed_at']=(now+timedelta(seconds=1)).isoformat()
    if case=='revoked': snapshot['revoked']=True
    if case=='disabled': binding=replace(binding,enabled=False)
    if case=='wildcard': binding=replace(binding,account_ref='*')
    if case=='installation': snapshot['installation_ref']='synthetic-new-installation'
    result=assess_sim_binding(snapshot,binding,now,synthetic=True)
    assert result['future_sim_eligible'] is (case=='proven_sim')
    assert result['external_order_authority'] is False and result['sim_execution_authority']=='DISABLED'
    assert result['evidence_kind']=='SYNTHETIC_OFFLINE'
    if case=='proven_real': assert result['sim_classification_status']=='PROVEN_NON_SIMULATION'
    # Even a perfect fictional proof cannot establish native classification.
    native=assess_sim_binding(snapshot,binding,now)
    assert native['sim_classification_status']=='UNKNOWN' and not native['future_sim_eligible']


def test_runtime_change_revokes_without_automatic_rebinding():
    binding,now,snapshot=fixture(); latch=OfflineBindingLatchV1(binding)
    assert latch.observe(snapshot,now)['future_sim_eligible']
    assert not latch.observe({**snapshot,'connection_ref':'synthetic-other'},now)['future_sim_eligible']
    assert not latch.observe(snapshot,now)['future_sim_eligible']


def test_snapshot_api_exposes_no_identifiers_or_callable_order_methods():
    binding,now,snapshot=fixture()
    result=assess_sim_binding(snapshot,binding,now)
    assert not any('ref' in k or 'digest' in k or 'sha256' in k for k in result)
    assert not any(callable(v) for v in result.values())


def test_current_snapshot_is_read_only_and_unknown_before_any_data(api_settings,tmp_path):
    current,_=service(tmp_path)
    before=dict(vars(current.gate))
    for _ in range(3):
        snapshot=current.get_snapshot()
        assert snapshot['sim_discovery_status']=='NOT_IMPLEMENTED_AUTHORITY_UNPROVEN'
        assert snapshot['sim_classification_status']=='UNKNOWN'
        assert snapshot['sim_binding_status']=='NOT_CONFIGURED'
        assert snapshot['sim_execution_authority']=='DISABLED'
    assert current._runtime is None and current.gate.closed_count==0
    assert vars(current.gate)==before
    current.shutdown()


@pytest.mark.parametrize('bad',[None, [], {}, False])
def test_malformed_proof_cannot_classify(bad):
    binding,now,snapshot=fixture()
    snapshot['classification']=bad
    assert not assess_sim_binding(snapshot,binding,now,synthetic=True)['future_sim_eligible']
