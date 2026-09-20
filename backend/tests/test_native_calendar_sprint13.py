"""Explicit synthetic template mutations; never emit native evidence."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from backend.market_data import native_calendar_review_v1 as review
from backend.tests.test_session_lifecycle_sprint12 import stamp
from backend.tests.test_current_paper_sprint10 import gate


@pytest.fixture
def spec_source(monkeypatch):
    root=ET.Element('NinjaTrader'); t=ET.SubElement(root,'TradingHours')
    ET.SubElement(t,'Name').text=review.TEMPLATE
    ET.SubElement(t,'TimeZone').text='Central Standard Time'
    ET.SubElement(t,'HolidaysSerializable'); ET.SubElement(t,'PartialHolidaysSerializable')
    raw=ET.tostring(root)
    digest=sha256(raw).hexdigest()
    monkeypatch.setattr(review,'TEMPLATE_SHA256',digest)
    spec=json.loads(Path('backend/tests/native_capture_spec_sprint13.json').read_text())
    spec['calendar_evidence_sha256']=digest
    return spec,raw


@pytest.mark.parametrize('bad', ['none','hash','provider','contract','timezone','label','fixture','expiry','coverage','holiday','window','naive','date_extension'])
def test_feed_and_calendar_binding_fail_closed(spec_source,bad):
    spec,raw=spec_source
    now=datetime(2026,9,22,tzinfo=timezone.utc)
    if bad=='hash': raw+=b' '
    if bad=='provider': spec['provider_enum']='Simulator'
    if bad=='contract': spec['contract']['contract']='NQ OTHER'
    if bad=='timezone': spec['contract']['source_timezone']='America/Chicago'
    if bad=='label': spec['contract']['bar_label']='OPEN'
    if bad=='fixture': spec['contract']['fixture']=True
    if bad=='expiry': spec['expiry']='2026-09-01'
    if bad=='coverage': spec['covered_dates'].pop()
    if bad=='holiday': spec['closed_dates']=['2026-09-22']
    if bad=='window': now+=timedelta(days=30)
    if bad=='naive': now=now.replace(tzinfo=None)
    if bad=='date_extension': spec['contract']['valid_until']='2026-09-29T00:00:00+00:00'
    if bad=='none':
        assert review.validate_native_spec(spec,raw,now)['loaded_native_calendar']=='PENDING_NATIVE_BINDING'
    else:
        with pytest.raises(ValueError): review.validate_native_spec(spec,raw,now)


def test_overnight_holiday_never_becomes_ordinary_civil_day(spec_source,monkeypatch):
    spec,raw=spec_source
    root=ET.fromstring(raw)
    row=ET.SubElement(root.find('.//PartialHolidaysSerializable'),'PartialHoliday')
    ET.SubElement(row,'Date').text='2026-09-22T00:00:00'
    raw=ET.tostring(root); digest=sha256(raw).hexdigest()
    monkeypatch.setattr(review,'TEMPLATE_SHA256',digest); spec['calendar_evidence_sha256']=digest
    with pytest.raises(ValueError,match='NATIVE_EXCEPTION_MAPPING_REQUIRED'):
        review.validate_native_spec(spec,raw,datetime(2026,9,22,tzinfo=timezone.utc))


def test_calendar_evidence_contains_full_native_override_constraints():
    authority=json.loads(Path('backend/tests/native_authority_sprint13.json').read_text())
    assert authority['source_sha256']==review.TEMPLATE_SHA256
    assert len(authority['NORMAL_WEEKLY_SESSIONS'])==5
    assert len(authority['exceptions_2026'])==13
    assert authority['native_calendar_certified'] is False
    for row in authority['exceptions_2026']:
        if row['kind']=='PartialHolidaysSerializable':
            assert row['IsEarlyEnd']=='true' and row['IsLateBegin']=='false'
            assert row['Constraint']['TradingDay']


@pytest.mark.parametrize('when,state,boundary,trading',[
    ('2026-09-14T15:59:00-05:00','OPEN','2026-09-14T21:00:00+00:00','2026-09-14'),
    ('2026-09-14T16:00:00-05:00','DAILY_MAINTENANCE','2026-09-14T22:00:00+00:00',None),
    ('2026-09-14T17:00:00-05:00','OPEN','2026-09-15T21:00:00+00:00','2026-09-15'),
    ('2026-09-18T16:00:00-05:00','WEEKEND_CLOSED','2026-09-20T22:00:00+00:00',None),
    ('2027-09-14T15:59:00-05:00','UNKNOWN',None,None)])
def test_next_boundary_and_trading_date_do_not_depend_on_ticks(when,state,boundary,trading):
    g,_=gate()
    assert review.ordinary_calendar_context(g.market_hours,stamp(when))==dict(state=state,next_boundary=boundary,trading_date=trading)


@pytest.mark.parametrize('mutation',['post_hello_contradiction','loss','alignment_then_wait'])
def test_sidecar_cannot_hide_later_contradiction(tmp_path,mutation):
    from backend.tests.test_native_certification_sprint12 import sidecar
    from backend.market_data.native_certification_v1 import certify_startup
    p=tmp_path/'synthetic.connection.jsonl'; row,hello=sidecar(p)
    later=json.loads(json.dumps(row)); later['sequence']=1
    later['event_time']=(hello+timedelta(seconds=1)).isoformat()
    later['callback_received_time']=later['event_time']
    later['payload'].update(callback_previous_price_status='Connected',callback_previous_connection_status='Connected')
    if mutation=='post_hello_contradiction': later['payload']['callback_price_status']='Connecting'
    if mutation=='loss': later['payload']['callback_price_status']='Disconnected'
    if mutation=='alignment_then_wait':
        later['event_time']=(hello-timedelta(seconds=1)).isoformat()
        later['callback_received_time']=later['event_time']
        later['payload'].update(decision='WAIT_STARTUP_ALIGNMENT',callback_price_status='Connecting',callback_connection_status='Connecting',
            callback_previous_price_status='Disconnected',callback_previous_connection_status='Disconnected')
    p.write_text(json.dumps(row)+'\n'+json.dumps(later)+'\n')
    with pytest.raises(ValueError): certify_startup(p,'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',hello,'SYNTHETIC_FIXTURE')


def test_cli_cannot_watch_or_initialize_runtime_without_loaded_calendar(tmp_path,monkeypatch):
    from backend.market_data.native_certification_v1 import main
    template=tmp_path/'synthetic.xml'; template.write_text('synthetic')
    spec=tmp_path/'spec.json'; spec.write_text(json.dumps({'calendar_evidence_file':str(template)}))
    monkeypatch.setattr(review,'validate_native_spec',lambda *args,**kwargs: {'loaded_native_calendar':'PENDING_NATIVE_BINDING'})
    monkeypatch.setattr('sys.argv',['capture','--spec',str(spec),'--directory',str(tmp_path/'does-not-exist'),
        '--state',str(tmp_path/'state.sqlite'),'--output',str(tmp_path/'report.json'),'--purpose','market_open'])
    with pytest.raises(SystemExit) as error: main()
    assert error.value.code==2
    assert not (tmp_path/'state.sqlite').exists() and not (tmp_path/'report.json').exists()
