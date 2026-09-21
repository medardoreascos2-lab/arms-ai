"""Offline source/health faults; no native activation or account access."""
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.market_data.exporter_identity_v1 import verify_exporter_source, BOUNDARY, AUTHORED_SHA256
from backend.market_data.analysis_startup_v1 import AnalysisStartupV1
from backend.market_data.fresh_native_adapter_v1 import FreshNativeAdapterV1
from backend.api.market_analysis_time_app_v1 import create_market_analysis_time_app_v1
from backend.tests.test_analysis_time_sprint15x import forbid_account_and_execution_construction

SOURCE = Path('integrations/ninjatrader/ArmsReadOnlyMarketV1.cs').resolve()
TAIL = Path('backend/tests/fixtures/ArmsReadOnlyMarketV1.generated.txt').read_text()


def test_committed_and_actual_generated_tail_and_format_variation():
    source = SOURCE.read_text()
    for text in (source, source+TAIL, source+TAIL.replace('\t', '    ').replace('input ,', 'input,')):
        result = verify_exporter_source(('\ufeff'+text.replace('\n','\r\n')).encode())
        assert result['authored_sha256'] == AUTHORED_SHA256
        assert result['compiled_assembly_attested'] is False


@pytest.mark.parametrize('mutation', [
    'handwritten','timing','provider','canonical','sidecar','connection','truncated','missing_boundary',
    'duplicated_boundary','before_boundary','after_region','inside_region','truncated_tail','split_keyword',
])
def test_source_and_boundary_mutations_fail_closed(mutation):
    source = SOURCE.read_text(); tail = TAIL
    if mutation == 'handwritten': source = source.replace('IsOverlay = true','IsOverlay = false')
    elif mutation == 'timing': source = source.replace('TimingEvidence.ReadPair()', 'null')
    elif mutation == 'provider': source = source.replace('ProviderName(feeds[0]) != ExpectedProvider', 'false')
    elif mutation == 'canonical': source = source.replace('arms.nt.market.v1','arms.nt.market.v2')
    elif mutation == 'sidecar': source = source.replace('output.WriteLine(line);','')
    elif mutation == 'connection': source = source.replace('STOP_CONNECTION_REGRESSION','CONTINUE')
    elif mutation == 'truncated': source = source[:-20]
    elif mutation == 'missing_boundary': tail = tail.replace(BOUNDARY,'')
    elif mutation == 'duplicated_boundary': tail += TAIL
    elif mutation == 'before_boundary': source += 'class Intruder {}\n'
    elif mutation == 'after_region': tail += 'class Intruder {}'
    elif mutation == 'inside_region': tail = tail.replace('return indicator.', 'Danger(); return indicator.')
    elif mutation == 'truncated_tail': tail = tail.replace('#endregion','')
    elif mutation == 'split_keyword': tail = tail.replace('return','ret urn')
    with pytest.raises(ValueError): verify_exporter_source((source+tail).encode())


class Harness:
    def __init__(self, tmp_path, monkeypatch):
        monkeypatch.setattr('backend.market_data.analysis_startup_v1.live_process_start',lambda pid: 42 if pid else None)
        self.now = 1000
        self.runtime = AnalysisStartupV1(run_id=str(uuid4()), installed_exporter=SOURCE,
                                        qpc_clock=lambda: ('offline',1000,self.now))
        self.folder = tmp_path/'inbox'
    def backend(self):
        self.runtime.poll()
        self.runtime.verify_backend(self.runtime.health(),self.runtime.pid)
    def frontend(self, **changes):
        values=dict(expected_pid=99,expected_start=42,actual_pid=99,http_status=200,
                    build_id='fresh-build',html='ANALYSIS ONLY ADAPTER_STATUS fresh-build')
        values.update(changes);self.runtime.verify_frontend(**values)
    def prepare(self):
        self.backend();self.frontend();self.runtime.prepare(self.folder)
    def tick(self):
        self.now += 1000;self.runtime.poll()
        self.runtime.observe_waiting(self.runtime.health(),self.runtime.pid)
    def finish(self, **changes):
        values=dict(backend_pid=self.runtime.pid,frontend_pid=99,dashboard_status=200,allow_activation=True)
        values.update(changes);self.runtime.finish_health(**values)


@pytest.mark.parametrize('fault',[
    'backend_identity','backend_dead','frontend_404','frontend_process','frontend_build','adapter_start',
    'old_empty_input','old_evidence','nonempty_input','stale_run','stale_waiting','heartbeat_stopped',
    'insufficient_intervals','final_frontend_failure','final_process_failure','expired_health',
])
def test_health_failures_latch_and_never_arm(tmp_path,monkeypatch,fault,forbid_account_and_execution_construction):
    h=Harness(tmp_path,monkeypatch);r=h.runtime
    with pytest.raises((ValueError,FileExistsError)):
        if fault in ('backend_identity','backend_dead'):
            r.poll();health=r.health()
            if fault=='backend_identity':health['run_id']=str(uuid4())
            else:health['worker_heartbeat']=0
            r.verify_backend(health,r.pid)
        else:
            h.backend()
            if fault.startswith('frontend_'):
                h.frontend(**{'frontend_404':{'http_status':404},'frontend_process':{'actual_pid':100},
                              'frontend_build':{'build_id':'old-build'}}[fault])
            else:
                h.frontend()
                if fault=='adapter_start':r.installed_exporter=tmp_path/'missing.cs'
                if fault in ('old_empty_input','old_evidence'):
                    h.folder.mkdir()
                    if fault=='old_evidence':(h.folder/'old.jsonl').write_text('{}')
                try:r.prepare(h.folder)
                except FileNotFoundError:raise ValueError('source missing')
                if fault=='nonempty_input':(h.folder/'unexpected').write_text('')
                h.tick()
                if fault in ('stale_run','stale_waiting','heartbeat_stopped'):
                    health=r.health()
                    if fault=='stale_run':health['run_id']=str(uuid4())
                    elif fault=='stale_waiting':h.now+=3000
                    r.observe_waiting(health,r.pid)
                if fault!='insufficient_intervals':h.tick();h.tick()
                if fault=='expired_health':h.now+=5001
                h.finish(**({'dashboard_status':404} if fault=='final_frontend_failure' else
                            {'frontend_pid':100} if fault=='final_process_failure' else {}))
    assert r.phase=='FAILED'
    assert r.adapter is None or r.adapter.activation_start is None
    r.poll();assert r.phase=='FAILED'


def test_allowance_starts_only_after_all_gates_and_uses_new_qpc_origin(tmp_path,monkeypatch,forbid_account_and_execution_construction):
    h=Harness(tmp_path,monkeypatch);h.prepare();r=h.runtime
    h.now += 901000
    for _ in range(3):h.tick()
    assert r.adapter.status=='WAITING' and r.adapter.activation_start is None
    h.finish()
    assert r.phase=='AWAITING_OPERATOR_ACTIVATION'
    assert r.adapter.activation_start==h.now and r.adapter.activation_start>r.adapter.start
    h.now+=900000;r.poll();assert r.adapter.status=='WAITING'
    h.now+=1;r.poll();assert r.adapter.status=='REVOKED'
    assert r.phase=='FAILED'


def test_offline_success_never_starts_allowance_and_get_cannot_arm(tmp_path,monkeypatch,forbid_account_and_execution_construction):
    h=Harness(tmp_path,monkeypatch);h.prepare()
    for _ in range(3):h.tick()
    h.finish(allow_activation=False)
    r=h.runtime
    assert r.phase=='OFFLINE_VALIDATED_UNARMED' and r.adapter.activation_start is None
    with TestClient(create_market_analysis_time_app_v1(runtime=r)) as client:
        for _ in range(3):
            health=client.get('/api/v2/market-analysis/health').json()
            assert not health['activation_allowance_started']
            view=client.get('/api/v2/market-analysis/time-profile').json()
            assert view['market_stream']=='NOT_LIVE' and view['order_submit_reachable'] is False
        for route in ('/api/v2/market-analysis/health','/api/v2/market-analysis/time-profile','/arm','/orders'):
            assert client.post(route,json={}).status_code in (404,405)
    assert r.phase=='FAILED'


def test_default_adapter_waits_unarmed_rejects_early_input(tmp_path):
    a=FreshNativeAdapterV1(directory=tmp_path, installed_exporter=SOURCE,qpc_clock=lambda:('test',1000,1000))
    assert a.activation_start is None
    (tmp_path/'unexpected.jsonl').write_text('{}')
    a.poll();assert a.status=='REVOKED' and a.reason=='INPUT_BEFORE_ACTIVATION_ALLOWANCE'
    with pytest.raises(ValueError):a.arm_activation()


def test_restart_has_no_waiting_state_recovery(tmp_path,monkeypatch):
    one=Harness(tmp_path,monkeypatch);one.prepare();one.tick()
    old=one.runtime.health()
    new=AnalysisStartupV1(run_id=str(uuid4()),installed_exporter=SOURCE,qpc_clock=lambda:('new',1000,5000))
    new.poll()
    with pytest.raises(ValueError):new.verify_backend(old,new.pid)
    assert new.phase=='FAILED' and new.adapter is None
