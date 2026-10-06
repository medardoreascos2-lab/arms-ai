"""Whole indicator callback harness plus compile against installed NT assemblies."""
import json
import os
from pathlib import Path
import subprocess
from hashlib import sha256

import pytest

SOURCE=Path('integrations/ninjatrader/ArmsReadOnlyL1V1.cs').resolve()
FRAMEWORK=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319'


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    root=tmp_path_factory.mktemp('l1-callbacks')
    source=root/'l1.cs'
    source.write_text(SOURCE.read_text().replace('DateTime.UtcNow','ManualClock.UtcNow'))
    target=root/'l1.exe'
    command=[str(FRAMEWORK/'csc.exe'),'/nologo','/langversion:5','/out:'+str(target),
        '/r:System.Core.dll','/r:System.Web.Extensions.dll','/r:System.ComponentModel.DataAnnotations.dll',str(source),
        str(Path('backend/tests/fixtures/native_l1_harness_v1.cs').resolve())]
    result=subprocess.run(command,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    return target


@pytest.fixture(scope='module')
def bounded_binary(tmp_path_factory):
    root=tmp_path_factory.mktemp('l1-bounded')
    source=root/'l1.cs'
    marker='private const long L1_STREAM_MAX_BYTES = 256L * 1024 * 1024;'
    authored=SOURCE.read_text()
    assert authored.count(marker)==1
    source.write_text(authored.replace('DateTime.UtcNow','ManualClock.UtcNow').replace(
        marker,'private const long L1_STREAM_MAX_BYTES = 8192L;'))
    target=root/'l1.exe'
    command=[str(FRAMEWORK/'csc.exe'),'/nologo','/langversion:5','/out:'+str(target),
        '/r:System.Core.dll','/r:System.Web.Extensions.dll','/r:System.ComponentModel.DataAnnotations.dll',str(source),
        str(Path('backend/tests/fixtures/native_l1_harness_v1.cs').resolve())]
    result=subprocess.run(command,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    return target


def run(binary,tmp_path,mode):
    result=subprocess.run([str(binary),mode,str(tmp_path)],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
    paths=sorted(tmp_path.glob('*.segment.*.l1.jsonl'))
    if not paths:
        paths=sorted(tmp_path.glob('*.l1.jsonl'))
    return [[json.loads(line) for line in p.read_text().splitlines()] for p in paths]


@pytest.mark.parametrize('mode,count',[('valid',1),('ask_first',1),('bid_update',2),('ask_update',2),
    ('duplicate',2),('connection_event',1),('startup_previous_disconnected',1),
    ('stale_connecting_callback',1),('transient_crossed',2)])
def test_native_two_sided_callbacks(binary,tmp_path,mode,count):
    rows=[row for segment in run(binary,tmp_path,mode) for row in segment]
    assert rows[0]['kind']=='HELLO' and rows[0]['sequence']==0
    assert rows[-1]['kind']=='TERMINAL'
    assert [r['sequence'] for r in rows]==list(range(len(rows)))
    quotes=[r for r in rows if r['kind']=='QUOTE']
    assert len(quotes)==count
    assert all(r['payload']['ask']>=r['payload']['bid']>0 for r in quotes)
    assert all(r['event_time'].endswith('Z') for r in rows)
    assert not any(
        r['kind']=='TERMINAL'
        and r['payload'].get('reason')=='CROSSED_QUOTE'
        for r in rows
    )
    assert all(set(r)=={'schema','session','sequence','event_time','kind','payload'} for r in rows)


@pytest.mark.parametrize('mode',['bid_only','last','stale_side','zero_bid','zero_ask','nan','infinity','crossed',
    'contract','provider','expected_provider','expiry','timezone','template','disconnected','playback',
    'tick','point','connection_identity','source_disconnect','historical'])
def test_invalid_or_half_quote_has_no_publication(binary,tmp_path,mode):
    streams=run(binary,tmp_path,mode)
    assert not any(r['kind']=='QUOTE' for rows in streams for r in rows)


def test_restart_has_new_session(binary,tmp_path):
    streams=run(binary,tmp_path,'restart')
    assert len(streams)==2 and streams[0][0]['session']!=streams[1][0]['session']


def test_capacity_rotates_before_limit_and_seals_manifest(bounded_binary,tmp_path):
    segments=run(bounded_binary,tmp_path,'capacity')
    paths=sorted(tmp_path.glob('*.segment.*.l1.jsonl'))
    rows=[row for segment in segments for row in segment]
    manifest=json.loads(next(tmp_path.glob('*.l1.manifest.json')).read_text())
    assert rows[0]['kind']=='HELLO'
    assert sum(row['kind']=='QUOTE' for row in rows)>1
    assert rows[-1]['kind']=='TERMINAL'
    assert rows[-1]['payload']['reason']=='SESSION_TERMINATED'
    assert [row['sequence'] for row in rows]==list(range(len(rows)))
    assert len(paths)==len(segments)>=2
    assert manifest['schema']=='arms.nt.l1.manifest.v1'
    assert manifest['state']=='TERMINATED'
    assert manifest['terminal_reason']=='SESSION_TERMINATED'
    assert manifest['session']==rows[0]['session']
    assert [item['index'] for item in manifest['segments']]==list(range(1,len(paths)+1))
    for path,item,segment in zip(paths,manifest['segments'],segments):
        raw=path.read_bytes()
        assert len(raw)<=8192
        assert item['sealed'] is True
        assert item['file']==path.name
        assert item['bytes']==len(raw)
        assert item['sha256']==sha256(raw).hexdigest()
        assert item['first_sequence']==segment[0]['sequence']
        assert item['last_sequence']==segment[-1]['sequence']
    assert 'CALLBACK_FAILED' not in SOURCE.read_text()


def test_provider_disconnect_preserves_exact_terminal_reason(binary,tmp_path):
    rows=[row for segment in run(binary,tmp_path,'source_disconnect') for row in segment]
    manifest=json.loads(next(tmp_path.glob('*.l1.manifest.json')).read_text())
    assert rows[-1]['kind']=='TERMINAL'
    assert rows[-1]['payload']['reason']=='PROVIDER_DISCONNECTED'
    assert manifest['terminal_reason']=='PROVIDER_DISCONNECTED'


def test_current_ninjatrader_sdk_compiles_exact_authored_body(tmp_path):
    sdk=Path('C:/Program Files/NinjaTrader 8/bin')
    custom=Path.home()/'OneDrive/Documents/NinjaTrader 8/bin/Custom/NinjaTrader.Custom.dll'
    assert custom.is_file() and (sdk/'NinjaTrader.Core.dll').is_file(), 'INSTALLED_SDK_REQUIRED'
    source=tmp_path/'l1.cs'
    source.write_text('extern alias NTBase;\nusing Indicator = NTBase::NinjaTrader.NinjaScript.Indicators.Indicator;\n'+SOURCE.read_text())
    refs=[sdk/'NinjaTrader.Core.dll',sdk/'NinjaTrader.Gui.dll',
        *(FRAMEWORK/'WPF'/n for n in ('WindowsBase.dll','PresentationCore.dll','PresentationFramework.dll')),
        'System.Core.dll','System.Web.Extensions.dll','System.ComponentModel.DataAnnotations.dll','System.Xaml.dll']
    result=subprocess.run([str(FRAMEWORK/'csc.exe'),'/nologo','/langversion:5','/target:library',
        '/out:'+str(tmp_path/'l1.dll'),*('/r:'+str(p) for p in refs),'/r:NTBase='+str(custom),str(source)],
        capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'CS0436' not in result.stdout+result.stderr


def test_exporter_has_no_account_or_order_surface():
    source=SOURCE.read_text()
    for token in ('Account.', 'Account.All', 'CreateOrder(', '.Submit(', '.Cancel(', '.Flatten('):
        assert token not in source
    assert 'MarketDataType.Last' not in source
