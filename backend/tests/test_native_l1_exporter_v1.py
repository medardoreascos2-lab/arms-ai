"""Whole indicator callback harness plus compile against installed NT assemblies."""
import json
import os
from pathlib import Path
import subprocess

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


def run(binary,tmp_path,mode):
    result=subprocess.run([str(binary),mode,str(tmp_path)],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
    return [[json.loads(line) for line in p.read_text().splitlines()] for p in tmp_path.glob('*.l1.jsonl')]


@pytest.mark.parametrize('mode,count',[('valid',1),('ask_first',1),('bid_update',2),('ask_update',2),
    ('duplicate',2),('connection_event',1),('startup_previous_disconnected',1),
    ('stale_connecting_callback',1)])
def test_native_two_sided_callbacks(binary,tmp_path,mode,count):
    rows=run(binary,tmp_path,mode)[0]
    assert rows[0]['kind']=='HELLO' and rows[0]['sequence']==0
    assert rows[-1]['kind']=='TERMINAL'
    assert [r['sequence'] for r in rows]==list(range(len(rows)))
    quotes=[r for r in rows if r['kind']=='QUOTE']
    assert len(quotes)==count
    assert all(r['payload']['ask']>=r['payload']['bid']>0 for r in quotes)
    assert all(r['event_time'].endswith('Z') for r in rows)
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
