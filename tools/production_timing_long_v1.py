"""Offline LONG-profile production sidecar verification.

Disk-backed LONG evidence is validated without granting admission, freshness,
clock authority, execution authority, or authenticity. Historical Sprint15W
production_timing_v1 remains frozen separately.
"""
import hashlib
import json
import uuid

from tools.native_timing_witness_v1 import parse, ticks, check_pair, MINUTE, TICKS_UNIX, IDENTITY

MAX_BYTES = 2_000_000
MAX_RECORDS = 256
PAIR_FIELDS = set(('schema session pair_sequence canonical_sequence canonical_sha256 kind '
    'source_bar_label callback emission qpc_frequency callback_index bar_index bars_ago '
    'state bars_in_progress first_tick provider contract instrument bars_type bars_value '
    'application_timezone template bar_label observation_only runtime_admission').split())
SEAL_FIELDS = set(('schema session records bytes sha256 canonical_records '
                  'canonical_writer_closed timing_writer_closed complete').split())


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def lines(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES and raw.endswith(b'\n'),
            'TRUNCATED_OR_OVERSIZE')
    result = raw.splitlines()
    require(0 < len(result) <= MAX_RECORDS, 'RECORD_LIMIT')
    return result


class _Parsed:
    def __init__(self, rows):
        self.rows = rows

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        return parse(self.rows[index])

    def __iter__(self):
        return (parse(raw) for raw in self.rows)


def adjudicate(canonical_raw, sidecar_raw, seal_raw, *, profile_id=None, window_sink=None):
    """Complete closed stream, exact bar bijection; at least three CLOSED bars.

    Intentionally does not decide freshness, session admission, or clock bounds.
    A template name binds the existing identity only, not loaded calendar contents.
    """
    result = dict(status='FAIL',production_exporter_emission_binding='NOT_PROVEN',
                  reference_bound='UNKNOWN',drift_bound='UNKNOWN',clock_preflight='UNKNOWN',
                  runtime_admission=False)
    try:
        if profile_id is None:
            canonical_lines = lines(canonical_raw)
            pair_lines = lines(sidecar_raw)
            canonical_hash = hashlib.sha256(canonical_raw).hexdigest()
            sidecar_hash = hashlib.sha256(sidecar_raw).hexdigest()
            sidecar_size = len(sidecar_raw)
        else:
            from tools.production_capture_profiles_v1 import profile
            limits = profile(profile_id)
            for stream in (canonical_raw, sidecar_raw):
                require(stream.profile_id == profile_id and 0 < len(stream) <= limits.maximum_native_records
                        and 0 < stream.size <= limits.maximum_native_bytes, 'PROFILE_LIMIT')
                stream.verify()
            canonical_lines, pair_lines = canonical_raw, sidecar_raw
            canonical_hash, sidecar_hash = canonical_raw.sha256, sidecar_raw.sha256
            sidecar_size = sidecar_raw.size
        canonical = _Parsed(canonical_lines)
        pairs = _Parsed(pair_lines)
        require(len(seal_raw) <= 4096, 'SEAL_SIZE')
        seal = parse(seal_raw)
        session = canonical[0]['session']
        require(str(uuid.UUID(session)) == session, 'SESSION_UUID')
        require(set(seal) == SEAL_FIELDS and seal['schema'] == 'arms.nt.production-timing.seal.v1', 'SEAL_SCHEMA')
        require(seal['session'] == session and seal['canonical_writer_closed'] is True
                and seal['timing_writer_closed'] is True and seal['complete'] is True, 'WRITER_CLOSURE')
        require(all(type(seal[k]) is int for k in ('records','bytes','canonical_records')),
                'SEAL_INTEGER')
        require(seal['records'] == len(pairs) and seal['bytes'] == sidecar_size
                and seal['sha256'] == sidecar_hash
                and seal['canonical_records'] == len(canonical), 'SEAL_INTEGRITY')
        require(canonical[0]['kind'] == 'HELLO' and canonical[-1]['kind'] == 'DISCONNECTED', 'CANONICAL_LIFECYCLE')
        hello = canonical[0]['payload']
        for key, value in dict(provider='Provider31',contract='NQ DEC26',instrument='NQ',
                timeframe='1m',trading_hours_template='CME US Index Futures ETH',source_timezone='UTC',bar_label='CLOSE').items():
            require(hello[key] == value, 'HELLO_IDENTITY')
        require(hello['realtime'] is True and hello['read_only'] is True, 'HELLO_AUTHORITY')
        def bars():
            for i, row in enumerate(canonical):
                require(set(row) == set('schema session sequence event_time kind payload'.split())
                        and row['schema'] == 'arms.nt.market.v1', 'CANONICAL_SCHEMA')
                require(row['session'] == session and type(row['sequence']) is int and row['sequence'] == i, 'CANONICAL_SEQUENCE')
                ticks(row['event_time'])
                if row['kind'] in ('FORMING','CLOSED'):
                    require(set(row['payload']) == set('bar_time open high low close volume'.split()), 'CANDLE_SCHEMA')
                    yield row, canonical_lines[i]
                elif 0 < i < len(canonical)-1:
                    require(row['kind'] == 'HEARTBEAT', 'CANONICAL_LIFECYCLE')
        forming = 0; closed = 0; prior = None; pending = None; previous = None; frequency = None
        windows = [] if window_sink is None else window_sink
        from itertools import zip_longest
        for i, (p, bar) in enumerate(zip_longest(pairs, bars())):
            require(p is not None and bar is not None, 'MISSING_OR_EXTRA_PAIR')
            row, raw = bar
            require(set(p) == PAIR_FIELDS and p['schema'] == 'arms.nt.production-timing.v1', 'PAIR_SCHEMA')
            for key in ('pair_sequence','canonical_sequence','qpc_frequency','callback_index','bar_index','bars_ago','bars_in_progress','bars_value'):
                require(type(p[key]) is int, 'PAIR_INTEGER')
            require(p['pair_sequence'] == i and p['canonical_sequence'] == row['sequence']
                    and p['session'] == session and p['kind'] == row['kind'], 'PAIR_ROW_BINDING')
            require(p['canonical_sha256'] == hashlib.sha256(raw).hexdigest(), 'CANONICAL_HASH')
            require(all(p[k] == v for k,v in IDENTITY.items()), 'PAIR_IDENTITY')
            require(p['observation_only'] is True and p['runtime_admission'] is False
                    and p['state'] == 'Realtime' and p['bars_in_progress'] == 0 and p['first_tick'] is True, 'CALLBACK_PROVENANCE')
            cb, em = p['callback'], p['emission']
            check_pair(cb); check_pair(em)
            require(p['qpc_frequency'] > 0 and (frequency is None or frequency == p['qpc_frequency']), 'QPC_FREQUENCY')
            frequency = p['qpc_frequency']
            require(cb['qpc_after'] <= em['qpc_before'] and cb['utc_ticks'] <= em['utc_ticks']
                    and em['utc'] == row['event_time'], 'EMISSION_PAIR_ORDER')
            if previous:
                require(previous['emission']['qpc_after'] <= em['qpc_before']
                        and previous['emission']['utc_ticks'] <= em['utc_ticks'], 'EMISSION_REGRESSION')
                if previous['callback'] != cb:
                    require(previous['emission']['qpc_after'] <= cb['qpc_before']
                            and previous['emission']['utc_ticks'] <= cb['utc_ticks'], 'CALLBACK_REGRESSION')
            require(p['source_bar_label'] == row['payload']['bar_time'], 'BAR_LABEL_BINDING')
            label = ticks(p['source_bar_label'])
            require(label % MINUTE == 0 and p['bar_index'] >= 0
                    and p['bar_index'] == p['callback_index']-p['bars_ago'], 'BAR_GEOMETRY')
            if p['kind'] == 'CLOSED':
                require(p['bars_ago'] == 1 and forming >= 2 and pending is None, 'CLOSED_WITHOUT_COMPLETE_FORMING')
                require(prior['bar_index'] == p['bar_index'] and prior['source_bar_label'] == p['source_bar_label'], 'CLOSED_FORMING_BINDING')
                require(cb['utc_ticks'] >= label, 'CLOSED_BEFORE_LABEL')
                pending = p; closed += 1
            else:
                require(p['bars_ago'] == 0, 'FORMING_INDEX')
                if forming:
                    require(p['bar_index'] == prior['bar_index']+1
                            and label == ticks(prior['source_bar_label'])+MINUTE, 'BAR_PROGRESSION')
                require((forming >= 2) == (pending is not None), 'MISSING_CLOSED')
                if pending:
                    require(pending['callback'] == cb and pending['callback_index'] == p['callback_index'], 'SAME_CALLBACK_PAIRING')
                pending = None; forming += 1; prior = p
            windows.append(dict(canonical_sequence=p['canonical_sequence'],kind=p['kind'],
                          canonical_row_sha256=p['canonical_sha256'],
                          implied_start_utc_ticks=ticks(p['source_bar_label'])-MINUTE,
                          host_utc_low_us=(p['emission']['utc_ticks']-TICKS_UNIX)//10,
                          host_utc_high_us=(p['emission']['utc_ticks']-TICKS_UNIX+9)//10,
                          mono_low_us=p['emission']['qpc_before']*1000000//frequency,
                          mono_high_us=(p['emission']['qpc_after']*1000000+frequency-1)//frequency))
            previous = p
        require(pending is None and closed >= 3, 'MINIMUM_CLOSED')
        result.update(status='PASS',production_exporter_emission_binding='PASS_STREAM_ONLY',
                      session=session,records=len(canonical),pairs=len(pairs),forming=forming,closed=closed,
                      qpc_frequency=frequency,sidecar_sha256=sidecar_hash,
                      canonical_sha256=canonical_hash,
                      first_callback=pairs[0]['callback'],last_emission=pairs[-1]['emission'],
                      emission_windows=windows if window_sink is None else [],
                      calendar_binding='EXISTING_TEMPLATE_IDENTITY_ONLY')
    except (ValueError,KeyError,TypeError,IndexError,AttributeError,OverflowError,RecursionError) as error:
        result['reason'] = str(error) if isinstance(error,ValueError) else 'MALFORMED_EVIDENCE'
    return result


def clock_epoch_binding(adjudication, *, run_id, epoch, bridges, measurements):
    """Offline clock-evidence manifest using shared Windows QPC, never perf_ns relabeling.

    Future acquisition must bracket each Clock Evidence probe with qpc_pair(),
    use the same fresh run UUID as its epoch, and hash raw output.
    Each bridge spans a raw probe's complete execution, not only its UTC read.
    Bounds deliberately remain unknown until independently reviewed authority exists.
    """
    require(adjudication['status'] == 'PASS', 'PRODUCTION_PAIRING_REQUIRED')
    require(str(uuid.UUID(run_id)) == run_id and epoch == run_id, 'CLOCK_EPOCH')
    require(len(bridges) == len(measurements) and len(bridges) >= 2, 'CLOCK_BRIDGES')
    first = adjudication['first_callback']['qpc_before']
    last = adjudication['last_emission']['qpc_after']
    f = adjudication['qpc_frequency']; previous = -1; observations = []
    for bridge, raw in zip(bridges,measurements):
        sample = parse(raw)
        require(sample['epoch'] == epoch, 'MEASUREMENT_EPOCH')
        require(bridge['measurement_sha256'] == hashlib.sha256(raw).hexdigest(), 'MEASUREMENT_HASH')
        a,b = bridge['before'],bridge['after']
        for p in (a,b):
            require(all(type(p[k]) is int for k in ('qpc_before','qpc_after','frequency','host_unix_ns'))
                    and p['frequency'] == f and 0 <= p['qpc_before'] <= p['qpc_after'], 'BRIDGE_PAIR')
        require(previous <= a['qpc_before'] <= a['qpc_after'] <= b['qpc_before'] <= b['qpc_after'], 'BRIDGE_ORDER')
        previous = b['qpc_after']
        observations.append(dict(measurement_sha256=bridge['measurement_sha256'],
            epoch=epoch,qpc_low=a['qpc_before'],qpc_high=b['qpc_after'],
            maximum_age_at_last_emission_us=max(0,(last-a['qpc_before'])*1000000+f-1)//f,
            available_at_last_emission=b['qpc_after'] <= last,
            reference_uncertainty=None,reviewed_drift_rate=None))
    require(bridges[0]['after']['qpc_after'] <= first and bridges[-1]['before']['qpc_before'] >= last, 'EPOCH_DOES_NOT_BRACKET_PRODUCTION')
    return dict(schema='arms.production-clock-binding.v1',run_id=run_id,epoch=epoch,
        exporter_session=adjudication['session'],canonical_sha256=adjudication['canonical_sha256'],
        sidecar_sha256=adjudication['sidecar_sha256'],qpc_frequency=f,observations=observations,
        production_emission_windows=adjudication['emission_windows'],
        reference_bound=None,drift_bound=None,clock_preflight='UNKNOWN',runtime_admission=False,
        measurement_quality='REQUIRES_CLOCK_EVIDENCE_VALIDATION_AND_REVIEWED_BOUNDS')


def acquire_clock_measurement(reference, address, epoch):
    """Explicit future acquisition only; never called by exporter or adjudication.

    Caller must already have authorization for a fresh bounded capture. DNS is
    outside this function; use Clock Evidence's bounded allowlisted resolver.
    """
    from tools import clock_evidence_v1 as evidence
    from tools.native_timing_witness_v1 import qpc_pair
    require(str(uuid.UUID(epoch)) == epoch, 'CLOCK_EPOCH')
    require(reference in evidence.REFERENCES, 'REFERENCE_NOT_ALLOWLISTED')
    before = qpc_pair()
    measurement = evidence.probe(reference,address,epoch,timeout=2)
    after = qpc_pair()
    raw = json.dumps(measurement,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    return raw, dict(before=before,after=after,measurement_sha256=hashlib.sha256(raw).hexdigest())
