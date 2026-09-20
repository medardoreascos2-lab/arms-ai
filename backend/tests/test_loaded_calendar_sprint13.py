"""Recorded metadata replay plus explicit mutation tests; no native activation."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from backend.market_data.loaded_calendar_binding_v1 import compare_loaded_calendar, verify_loaded_binding, NATIVE_SHA256
from backend.market_data import native_calendar_review_v1 as review


@pytest.fixture
def witness():
    report=json.loads(Path('backend/tests/loaded_calendar_adjudication_sprint13.json').read_text())
    ref=report['static_reference']; e=report['native_record']
    root=ET.Element('NinjaTrader'); t=ET.SubElement(root,'TradingHours')
    for key,value in [('Name',ref['name']),('TimeZone',ref['timezone']),('Version',ref['version'])]:
        ET.SubElement(t,key).text=str(value)
    def session(parent,tag,s):
        node=ET.SubElement(parent,tag)
        for key,field in [('BeginDay','begin_day'),('BeginTime','begin_time'),('EndDay','end_day'),('EndTime','end_time'),('TradingDay','trading_day')]:
            ET.SubElement(node,key).text=str(s[field])
    sessions=ET.SubElement(t,'Sessions')
    for s in ref['sessions']: session(sessions,'Session',s)
    full=ET.SubElement(t,'HolidaysSerializable')
    for d in ref['holiday_dates']: ET.SubElement(ET.SubElement(full,'Holiday'),'Date').text=d+'T00:00:00'
    partial=ET.SubElement(t,'PartialHolidaysSerializable')
    overrides={r['date']:r for r in ref['partial_holidays_2026']}
    for d in ref['partial_holiday_dates']:
        row=ET.SubElement(partial,'PartialHoliday'); ET.SubElement(row,'Date').text=d+'T00:00:00'
        if d in overrides:
            r=overrides[d]; session(row,'Constraint',r['constraint'])
            ET.SubElement(row,'IsEarlyEnd').text=str(r['early_end']).lower()
            ET.SubElement(row,'IsLateBegin').text=str(r['late_begin']).lower()
            ss=ET.SubElement(row,'Sessions')
            for s in r['sessions']: session(ss,'Session',s)
    raw=(json.dumps(e,separators=(',',':'),ensure_ascii=False)+'\r\n').encode()
    assert sha256(raw).hexdigest()==NATIVE_SHA256  # Exact native serialization, not fabricated output.
    return e,ET.tostring(root),raw


def test_recorded_native_metadata_matches_independent_static_reference(witness):
    e,template,raw=witness
    result=verify_loaded_binding(raw,template)
    assert result['ordinary_binding']=='PASS'
    assert (result['weekly_sessions'],result['iterator_samples'],result['full_holiday_dates'],result['partial_holiday_dates'],result['partial_constraints_2026'])==(5,13,31,112,11)
    assert result['holiday_runtime_admission'].startswith('BLOCKED')
    assert result['direct_loaded_xml_hash']=='NOT_EXPOSED'


@pytest.mark.parametrize('change',['schema','version','timezone','instrument','contract','bars','utc','weekly','holiday','partial_dates',
    'early_close','dst','trading_date','utc_kind','end_inclusion','missing_sample','reordered_sample','boundary'])
def test_any_semantic_mismatch_fails_closed(witness,change):
    e,template,_=witness; e=deepcopy(e)
    fields={'schema':'wrong','version':999,'timezone':'UTC','instrument':'ES','contract':'NQ OTHER','bars':5,'utc':'Eastern Standard Time'}
    keys={'schema':'schema','version':'template_version','timezone':'template_timezone','instrument':'instrument','contract':'contract','bars':'bars_value','utc':'application_timezone'}
    if change in keys: e[keys[change]]=fields[change]
    if change=='weekly': e['sessions'][0]['begin_time']=1800
    if change=='holiday': e['holiday_dates'].pop()
    if change=='partial_dates': e['partial_holiday_dates'].pop()
    if change=='early_close': e['partial_holidays_2026'][0]['constraint']['end_time']=1600
    if change=='dst': e['samples'][6]['begin']='2026-11-01T22:00:00.0000000Z'
    if change=='trading_date': e['samples'][2]['trading_day']='2026-09-21'
    if change=='utc_kind': e['samples'][0]['begin_kind']='Unspecified'
    if change=='end_inclusion': e['samples'][1]['includes_end']=False
    if change=='missing_sample': e['samples'].pop()
    if change=='reordered_sample': e['samples'].reverse()
    if change=='boundary': e['samples'][1]['end']='2026-09-21T22:00:00.0000000Z'
    with pytest.raises(ValueError): compare_loaded_calendar(e,template)


@pytest.mark.parametrize('change',['truncate','newline','duplicate','alter'])
def test_raw_native_hash_is_not_a_user_assertion(witness,change):
    _,template,raw=witness
    bad={'truncate':raw[:-20],'newline':raw.rstrip(),'duplicate':raw+raw,'alter':raw.replace(b'Provider31',b'Other')+b' '}[change]
    with pytest.raises(ValueError): verify_loaded_binding(bad,template)


def test_bound_ordinary_spec_clears_gate_without_enabling_holidays(witness,monkeypatch):
    _,template,raw=witness
    # Static fixture serialization is intentionally different from private XML.
    digest=sha256(template).hexdigest(); monkeypatch.setattr(review,'TEMPLATE_SHA256',digest)
    spec=json.loads(Path('backend/tests/native_capture_spec_sprint13.json').read_text())
    spec['calendar_evidence_sha256']=digest
    now=datetime(2026,9,22,tzinfo=timezone.utc)
    assert review.validate_native_spec(spec,template,now,loaded_calendar_bytes=raw)['loaded_native_calendar']=='PASS'
    assert review.validate_native_spec(spec,template,now)['loaded_native_calendar']=='PENDING_NATIVE_BINDING'
    spec['loaded_calendar_evidence_sha256']='0'*64
    with pytest.raises(ValueError): review.validate_native_spec(spec,template,now,loaded_calendar_bytes=raw)


def test_end_inclusive_iterator_does_not_admit_a_maintenance_forming_bar(witness):
    from backend.tests.test_current_paper_sprint10 import gate
    from backend.market_data.session_state_v1 import SessionStateAuthorityV1
    e,_,_=witness
    probe=e['samples'][1]
    close=datetime.fromisoformat(probe['end'])
    g,_=gate(start=close)
    assert SessionStateAuthorityV1(g.market_hours).resolve(close).state=='DAILY_MAINTENANCE'
    assert probe['trading_day']=='2026-09-21'
