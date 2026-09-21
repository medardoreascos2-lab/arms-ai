"""Offline contract and HTTP boundary only; no native account access."""
from dataclasses import asdict
from datetime import timedelta
import ast
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from backend.api.current_paper_app_v1 import create_current_paper_app_v1
from backend.market_data.sim_binding_contract_v1 import (
    OfflineBindingLatchV1, PrivateBindingV1, assess_sim_binding,
    native_sim_status, validate_private_binding,
)
from backend.tests.test_sim_binding_sprint13 import fixture
from backend.tests.test_current_paper_sprint10 import service, api_settings


def latch_for(binding, snapshot):
    return OfflineBindingLatchV1(binding, runtime_ref=snapshot['runtime_ref'],
        connection_epoch=snapshot['connection_epoch'])


@pytest.mark.parametrize('case', ['valid', 'restart', 'reconnect', 'disconnect', 'duplicate',
    'out_of_order', 'gap', 'clock_regression', 'stale', 'future', 'account_changed',
    'provider_changed', 'configuration_changed', 'multiple', 'none', 'non_sim', 'unknown'])
def test_lifecycle_requires_binding_and_fresh_runtime_proof(case):
    binding, now, snap = fixture()
    latch = latch_for(binding, snap)
    assert latch.observe(snap, now)['future_sim_eligible']
    next_snap = {**snap, 'discovery_sequence': 1, 'observed_at': (now+timedelta(seconds=1)).isoformat()}
    changes = {
        'restart': {'runtime_ref':'synthetic-process-B'},
        'reconnect': {'connection_epoch':'synthetic-epoch-B'},
        'disconnect': {'connected':False}, 'duplicate': {'discovery_sequence':0},
        'out_of_order': {'discovery_sequence':-1}, 'gap': {'discovery_sequence':2},
        'clock_regression': {'observed_at':(now-timedelta(seconds=1)).isoformat()},
        'stale': {'observed_at':(now-timedelta(seconds=16)).isoformat()},
        'future': {'observed_at':(now+timedelta(seconds=2)).isoformat()},
        'account_changed': {'account_ref':'synthetic-account-B'},
        'provider_changed': {'provider':'Provider31'},
        'configuration_changed': {'configuration_sha256':'0'*64},
        'multiple': {'account_count':2}, 'none': {'account_count':0},
        'non_sim': {'classification':'PROVEN_NON_SIMULATION'}, 'unknown': {'classification':'UNKNOWN'},
    }
    result = latch.observe({**next_snap, **changes.get(case, {})}, now+timedelta(seconds=1))
    assert result['future_sim_eligible'] is (case == 'valid')
    assert result['sim_runtime_revalidation'] == ('SYNTHETIC_PASS' if case == 'valid' else 'REVOKED')
    assert result['sim_execution_authority'] == 'DISABLED'
    assert not result['external_order_authority']
    if case != 'valid':
        assert not latch.observe(next_snap, now+timedelta(seconds=1))['future_sim_eligible']


def test_restart_cannot_resume_prior_sequence_and_explicit_revocation_is_latched():
    binding, now, snap = fixture()
    assert not latch_for(binding, snap).observe({**snap,'discovery_sequence':5}, now)['future_sim_eligible']
    latch = latch_for(binding, snap)
    latch.revoke()
    assert not latch.observe(snap, now)['future_sim_eligible']


def private_draft():
    binding = PrivateBindingV1('a'*64,'b'*64,'Simulator','c'*64,'d'*64,'UNRESOLVED_NATIVE_PROOF')
    return {**asdict(binding),'schema':'arms.private-sim-binding.v1','configuration_sha256':binding.digest()}


@pytest.mark.parametrize('case', ['valid','wildcard','list','extra','enabled','name','digest','proof','provider_type'])
def test_private_draft_is_single_opaque_inert_binding(case):
    draft = private_draft()
    if case == 'wildcard': draft['account_ref']='*'
    if case == 'list': draft=[draft]
    if case == 'extra': draft['account_name']='SYNTHETIC_PRIVATE'
    if case == 'enabled': draft['enabled']=True
    if case == 'name': draft['account_ref']='SYNTHETIC_PRIVATE'
    if case == 'digest': draft['configuration_sha256']='0'*64
    if case == 'proof': draft['proof_contract']='SIM101_NAME'
    if case == 'provider_type': draft['provider']=True
    result=validate_private_binding(draft)
    assert (result is not None) is (case == 'valid')
    if result:
        assert result.enabled is False
        assert assess_sim_binding({},result,fixture()[1])['sim_classification_status']=='UNKNOWN'


class ForbiddenHandle:
    def __getattribute__(self, name):
        raise AssertionError('handle invoked')
    def __eq__(self, other):
        raise AssertionError('handle compared')


def test_scalar_boundary_rejects_handles_without_invoking_them():
    binding, now, snap=fixture()
    for key in snap:
        result=assess_sim_binding({**snap,key:ForbiddenHandle()},binding,now,synthetic=True)
        assert not result['future_sim_eligible']
    assert not assess_sim_binding(ForbiddenHandle(),binding,now)['future_sim_eligible']
    assert validate_private_binding({**private_draft(),'account_ref':ForbiddenHandle()}) is None


def test_sim_boundary_has_no_native_bridge_io_or_mutation_capability():
    tree=ast.parse(Path('backend/market_data/sim_binding_contract_v1.py').read_text())
    allowed_imports={'dataclasses','datetime','hashlib','json','re'}
    forbidden={'open','exec','eval','compile','__import__','Submit','Cancel','CancelAllOrders',
        'Change','Flatten','CreateOrder','ResetSimulationAccount','submit_order','cancel_order',
        'open_position','close_position','Account','Connection'}
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            assert all(alias.name in allowed_imports for alias in node.names)
        if isinstance(node,ast.ImportFrom): assert node.module in allowed_imports
        if isinstance(node,ast.Call):
            name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
            assert name not in forbidden


def test_native_claims_cannot_be_promoted_by_any_combination_of_weak_factors():
    binding, now, snap=fixture()
    for classification in ('PROVEN_SIMULATION','PROVEN_NON_SIMULATION','UNKNOWN'):
        for label in ('Sim101','Sim-looking-real','Playback101'):
            result=assess_sim_binding({**snap,'classification':classification,'name':label,
                'provider':'Simulator','operator_approved':True},binding,now)
            assert result['sim_classification_status']=='UNKNOWN'
            assert not result['future_sim_eligible']


def test_status_gets_have_no_runtime_or_account_side_effects(api_settings,tmp_path,monkeypatch):
    current,_=service(tmp_path)
    def forbidden(*args,**kwargs):
        raise AssertionError('control invoked by GET')
    monkeypatch.setattr(current,'control',forbidden)
    before=dict(vars(current.gate))
    app=create_current_paper_app_v1(service=current)
    with TestClient(app) as client:
        for _ in range(3):
            assert client.get('/api/v2/paper/sim-readiness').json()==native_sim_status()
            snapshot=client.get('/api/v2/backtesting/dashboard').json()['paper_research']
            for key,value in native_sim_status().items(): assert snapshot[key]==value
            assert current._runtime is None and vars(current.gate)==before
        assert not (tmp_path/'current.sqlite').exists()
    public=json.dumps(native_sim_status())
    assert not any(s in public for s in ('account_ref','connection_ref','digest','SYNTHETIC_PRIVATE'))


def test_reviewed_audit_cannot_claim_native_authority():
    audit=json.loads(Path('backend/tests/account_authority_sprint14.json').read_text())
    assert audit['native_proof_mechanisms_accepted']==[]
    assert audit['account_instances_accessed']==0 and not audit['discovery_implemented']
    assert audit['classification']=='UNKNOWN'
    assert audit['raw_account_has_mutators'] is True
    assert all(v is False for v in audit['boundary_mutators_reachable'].values())
