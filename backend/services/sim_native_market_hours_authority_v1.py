"""Bounded SIM_NATIVE calendar authority. Reads never publish or renew anything.

The HMAC attests operator review, not a NinjaTrader digital signature. The
embedded exact witness bytes remain independently checked against the reviewed
template. V1 rejects every exception-adjacent date rather than guessing mapping.
"""
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from backend.market_data.loaded_calendar_binding_v1 import CHICAGO, compare_loaded_calendar
from backend.market_data.native_calendar_review_v1 import TEMPLATE, TEMPLATE_SHA256
from backend.market_data.fresh_native_adapter_v1 import local_path
from backend.services import sim_native_authority_v3 as auth
from backend.services.sim_admission_envelope_v3 import utc_us
from backend.services.certified_market_hours_snapshot_loader_v2 import CertifiedMarketHoursSnapshotLoaderV2
from backend.services.certified_market_hours_runtime_provider_v2 import CertifiedMarketHoursRuntimeProviderV2

SCHEMA = 'ARMS_SIM_NATIVE_MARKET_HOURS_AUTHORITY_V1'
DOMAIN = b'arms.sim-native.market-hours.v1\0'
MAX_AGE = timedelta(minutes=30)
MAX_LIFE = timedelta(hours=48)
RISK = 'f43202dbb2d7b29fadff83487e589e5495df0bcd7898a660ab09de27c7282d0e'
POLICY = '34627eb6ffb4a714fc6714a0a6125b7ba9e0db292b280d6075eac54c9165075f'
PINS = dict(backend_account_id='SIM_NATIVE-917E15181DBB4F8F8D625716795704A3',
    execution_domain='SIM_NATIVE', native_account='Sim101', provider='Simulator',
    instrument='NQ DEC26', instrument_root='NQ', runtime_generation='1', risk_version=RISK)
WITNESS_FIELDS = set(('schema session event_time observation_only contract expiry_month instrument tick_size '
    'point_value bars_type bars_value application_timezone system_timezone template template_version '
    'template_timezone sessions holiday_dates partial_holiday_dates partial_holidays_2026 samples '
    'completion native_certification').split())
SAMPLE_FIELDS = set('query_configured_time includes_end begin begin_kind end end_kind trading_day'.split())
FIELDS = set(PINS) | set(('schema version authority_id configuration_generation commissioning_policy_id '
    'template_name template_timezone application_timezone calendar_witness_sha256 calendar_witness_utf8 '
    'issued_us expires_us covered_dates closed_dates special_hours').split())


def require(value, reason):
    if not value:
        raise ValueError(reason)


def _unique(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, 'DUPLICATE_FIELD')
        result[k] = v
    return result


def parse(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 200_000, 'ARTIFACT_SIZE')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_unique,
            parse_constant=lambda _: require(False, 'NONFINITE_VALUE'))
    except RecursionError as error:
        raise ValueError('ARTIFACT_NESTING') from error


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def review_witness(raw, template, *, issued):
    require(hashlib.sha256(template).hexdigest() == TEMPLATE_SHA256, 'TEMPLATE_CHANGED')
    require(raw.endswith(b'\n') and len(raw.splitlines()) == 1, 'WITNESS_INCOMPLETE')
    w = parse(raw)
    require(type(w) is dict and set(w) == WITNESS_FIELDS, 'WITNESS_SCHEMA')
    require(type(w['samples']) is list and all(type(s) is dict and set(s) == SAMPLE_FIELDS
            for s in w['samples']), 'SAMPLE_SCHEMA')
    require(type(w['system_timezone']) is str and bool(w['system_timezone']), 'SYSTEM_TIMEZONE')
    session_fields = set('begin_day begin_time end_day end_time trading_day'.split())
    sessions = list(w['sessions'])
    for row in w['partial_holidays_2026']:
        require(type(row) is dict and set(row) == {'date','early_end','late_begin','constraint','sessions'}
                and type(row['early_end']) is bool and type(row['late_begin']) is bool, 'PARTIAL_SCHEMA')
        sessions += [row['constraint'], *row['sessions']]
    require(all(type(s) is dict and set(s) == session_fields
        and all(type(s[k]) is int for k in ('begin_time','end_time'))
        and all(type(s[k]) is str for k in ('begin_day','end_day','trading_day')) for s in sessions), 'SESSION_SCHEMA')
    observed = datetime.fromisoformat(w['event_time'])
    require(observed.tzinfo is not None and observed.utcoffset() == timedelta(0)
            and timedelta(0) <= issued - observed <= MAX_AGE, 'WITNESS_STALE_OR_FUTURE')
    # Reuse semantic comparison, not the old witness's fixed digest/freshness.
    compare_loaded_calendar(w, template)
    require(w['template'] == TEMPLATE and w['template_timezone'] == 'Central Standard Time'
            and w['application_timezone'] == 'UTC', 'TEMPLATE_IDENTITY')
    return w


def snapshot(w, issued, days):
    require(type(days) is int and 1 <= days <= 3, 'COVERAGE_LIMIT')
    first = issued.astimezone(CHICAGO).date()
    dates = [first + timedelta(days=n) for n in range(days)]
    require(all(d.year == 2026 for d in dates) and dates[-1] < date(2026, 12, 1), 'CONTRACT_COVERAGE')
    affected = {date.fromisoformat(d) + timedelta(days=n)
        for d in w['holiday_dates'] + w['partial_holiday_dates'] for n in (-1, 0, 1)}
    require(not affected.intersection(dates), 'UNSUPPORTED_EXCEPTION_MAPPING')
    value = dict(covered_dates=[d.isoformat() for d in dates], closed_dates=[], special_hours=[])
    provider(value)  # The existing loader owns all civil-date snapshot semantics.
    return value


def provider(value):
    c, s = CertifiedMarketHoursSnapshotLoaderV2().load_from_mapping(raw=value)
    return CertifiedMarketHoursRuntimeProviderV2(calendar_snapshot=c, special_hours_snapshot=s)


def identity(config, policy_id, key):
    require(policy_id == POLICY, 'POLICY_MISMATCH')
    require(all(config.get(k) == v for k, v in PINS.items() if k != 'instrument_root'), 'CONFIG_BINDING')
    require(config.get('authority_id') == auth.authority_id(key), 'AUTHORITY_MISMATCH')
    generation = config.get('configuration_generation')
    require(type(generation) is str and generation.isascii() and generation.isdecimal()
            and str(int(generation)) == generation and int(generation) > 0, 'CONFIG_GENERATION')
    return {**PINS, 'authority_id': config['authority_id'], 'configuration_generation': generation,
            'commissioning_policy_id': policy_id}


def build(raw, template, *, config, policy_id, key, now, days=3):
    utc_us(now)
    w = review_witness(raw, template, issued=now)
    s = snapshot(w, now, days)
    end = datetime.combine(date.fromisoformat(s['covered_dates'][-1]) + timedelta(days=1), time(), CHICAGO)
    expires = min(now + MAX_LIFE, end.astimezone(timezone.utc))
    value = dict(schema=SCHEMA, version=1, **identity(config, policy_id, key),
        template_name=TEMPLATE, template_timezone='Central Standard Time', application_timezone='UTC',
        calendar_witness_sha256=hashlib.sha256(raw).hexdigest(), calendar_witness_utf8=raw.decode('utf-8'),
        issued_us=utc_us(now), expires_us=utc_us(expires), **s)
    payload = canonical(value)
    return payload, hmac.new(key, DOMAIN + payload, hashlib.sha256).hexdigest().encode('ascii')


def verify(payload, signature, template, *, config, policy_id, key, now):
    require(hmac.compare_digest(signature, hmac.new(key, DOMAIN + payload, hashlib.sha256).hexdigest().encode('ascii')), 'HMAC_INVALID')
    v = parse(payload)
    require(type(v) is dict and set(v) == FIELDS and canonical(v) == payload, 'PACKAGE_SCHEMA')
    require(v['schema'] == SCHEMA and type(v['version']) is int and v['version'] == 1, 'PACKAGE_VERSION')
    require(all(type(v[k]) is type(x) and v[k] == x for k, x in identity(config, policy_id, key).items()), 'PACKAGE_BINDING')
    require(type(v['issued_us']) is int and type(v['expires_us']) is int, 'PACKAGE_TIME')
    require(0 < v['issued_us'] <= utc_us(now) < v['expires_us'], 'EXPIRED_OR_FUTURE')
    issued = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=v['issued_us'])
    raw = v['calendar_witness_utf8'].encode('utf-8')
    require(hashlib.sha256(raw).hexdigest() == v['calendar_witness_sha256'], 'WITNESS_DIGEST')
    # Re-derive the entire package, including exact expiry and exception quarantine.
    require(type(v['covered_dates']) is list, 'COVERAGE_SCHEMA')
    expected, _ = build(raw, template, config=config, policy_id=policy_id, key=key,
                        now=issued, days=len(v['covered_dates']))
    require(expected == payload, 'PACKAGE_CONTENT_CHANGED')
    s = {k: v[k] for k in ('covered_dates', 'closed_dates', 'special_hours')}
    require(now.astimezone(CHICAGO).date().isoformat() in v['covered_dates'], 'OUTSIDE_CERTIFIED_COVERAGE')
    return v, provider(s)


def private_path(value):
    """Read-only ACL check: current user/SYSTEM ownership and no other grantees."""
    path = local_path(auth.safe_path(value, authority=True))
    environment = dict(os.environ, ARMS_HOURS_ACL_PATH=str(path))
    result = subprocess.run([str(Path(os.environ['WINDIR'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),
        '-NoProfile', '-NonInteractive', '-Command',
        "$ErrorActionPreference='Stop';$a=Get-Acl -LiteralPath $env:ARMS_HOURS_ACL_PATH;"
        "$s=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;"
        "if($a.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $s){exit 1};"
        "$r=@($a.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]));"
        "if($r.Count -eq 0){exit 1};foreach($x in $r){"
        "if($x.IdentityReference.Value -notin @($s,'S-1-5-18')){exit 1}}"],
        env=environment, capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    require(result.returncode == 0, 'PRIVATE_PATH_REQUIRED')
    return path


def read_bounded(path):
    with private_path(path).open('rb') as stream:
        raw = stream.read(200_001)
    require(len(raw) <= 200_000, 'ARTIFACT_SIZE')
    return raw


def production_template():
    # Exact reviewed template contents, never an operator-supplied schedule.
    path = Path.home()/'OneDrive/Documents/NinjaTrader 8/templates/TradingHours'/ (TEMPLATE + '.xml')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == TEMPLATE_SHA256, 'TEMPLATE_CHANGED')
    return raw


class SimNativeMarketHoursLifecycleV1:
    """SIM-only replacement for provider lookup; authenticate on every lookup.

    No last-known-good cache: removal, tampering, config drift or expiry revokes
    the next admission. No fallback to environment/fixture/PAPER providers.
    """
    def __init__(self, *, context, clock):
        self.context, self.clock = context, clock

    @staticmethod
    def unavailable():
        return dict(status='UNAVAILABLE', reason='AUTHORITY_UNAVAILABLE', market_open=False)

    def inspect(self):
        try:
            root = auth.authority_root()/'authority-inputs'
            payload = read_bounded(root/'market-hours-v1.json')
            signature = read_bounded(root/'market-hours-v1.sig')
            template, key = production_template(), auth.load_authority()
            config, policy_id = self.context(self.clock())
            # ACL/key/config I/O can cross an expiry or Chicago date boundary.
            now = self.clock()
            v, p = verify(payload, signature, template, config=config, policy_id=policy_id, key=key, now=now)
            opened = p.get_market_hours_service().is_market_open(symbol='NQ', timestamp=now)
            view = dict(status='MARKET_OPEN_CERTIFIED' if opened else 'MARKET_CLOSED', reason=None,
                market_open=opened, covered_dates=v['covered_dates'], current_chicago_date=now.astimezone(CHICAGO).date().isoformat(),
                template_name=v['template_name'], package_age_seconds=(utc_us(now)-v['issued_us'])/1_000_000,
                expires_us=v['expires_us'])
            return view, p
        except FileNotFoundError:
            return dict(status='WITNESS_REQUIRED', reason='PACKAGE_MISSING', market_open=False), None
        except (ValueError, OSError, TypeError, KeyError, OverflowError, AttributeError, RecursionError, ET.ParseError, subprocess.SubprocessError) as error:
            reason = str(error)
            status = {'EXPIRED_OR_FUTURE': 'EXPIRED', 'OUTSIDE_CERTIFIED_COVERAGE': 'OUTSIDE_CERTIFIED_COVERAGE'}.get(reason, 'UNAVAILABLE')
            return dict(status=status, reason='AUTHORITY_INVALID' if status == 'UNAVAILABLE' else status, market_open=False), None

    def get_active_provider(self):
        return self.inspect()[1]

    def get_snapshot(self):
        return self.inspect()[0]
