"""Bounded LOCAL PAPER launcher; fresh native files only, loopback read-only API.

Run from repository root. Native activation is always an operator action.
No profile defaults, native account discovery, replay catch-up or automatic resume.
"""
import argparse
from datetime import date, datetime, time as wall_time, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
from threading import Thread
import time
from uuid import UUID, uuid4

from backend.backtesting.current_paper_runtime_v1 import CurrentPaperServiceV1
from backend.backtesting.operational_paper_v1 import OperationalPaperV1
from backend.backtesting.paper_research_v1 import PaperResearchConfigV1
from backend.config.api_settings import APISettings
from backend.market_data.current_candle_authority_v1 import CurrentCandleAuthorityV1, CurrentFeedContractV1
from backend.market_data.native_calendar_review_v1 import validate_native_spec, ordinary_calendar_context
from backend.market_data.ninjatrader_market_reader_v1 import _object, _utc
from backend.services.certified_market_calendar_v2 import CertifiedCalendarSnapshotV2
from backend.services.certified_market_hours_runtime_provider_v2 import CertifiedMarketHoursRuntimeProviderV2
from backend.services.special_hours_snapshot_v2 import CertifiedSpecialHoursSnapshotV2, CertifiedSpecialHoursWindowV2
from backend.services.certified_economic_news_snapshot_loader_v2 import CertifiedEconomicNewsSnapshotLoaderV2
from backend.services.economic_news_runtime_provider_v2 import EconomicNewsRuntimeProviderV2


RISK_KEYS = frozenset({
    'ARMS_MAXIMUM_QUOTE_AGE_SECONDS','ARMS_MINIMUM_REWARD_RISK_RATIO','ARMS_MINIMUM_STOP_POINTS',
    'ARMS_MAXIMUM_STOP_POINTS','ARMS_MAXIMUM_SPREAD_POINTS','ARMS_MINIMUM_ATR_POINTS',
    'ARMS_MINIMUM_A_PLUS_PROBABILITY','ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE',
    'ARMS_MAXIMUM_SIGNAL_AGE_SECONDS','ARMS_MAXIMUM_OPEN_POSITIONS'})


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=_object)


def review(spec_path, now):
    spec=read_json(spec_path)
    result=validate_native_spec(spec,Path(spec['calendar_evidence_file']).read_bytes(),now,
        loaded_calendar_bytes=Path(spec['loaded_calendar_evidence_file']).read_bytes())
    if result['loaded_native_calendar']!='PASS':
        raise ValueError('LOADED_CALENDAR_UNPROVEN')
    certificate=read_json('backend/tests/market_open_native_certification_sprint13.json')
    for name,digest in certificate['reviewed_source_sha256'].items():
        if sha256(Path(name).read_bytes()).hexdigest()!=digest:
            raise ValueError('CERTIFIED_SOURCE_CHANGED')
    return spec


def make_authorities(spec, settings, clock):
    contract=CurrentFeedContractV1(**{**spec['contract'],
        'provider':'NINJATRADER:'+spec['provider_enum'],
        'valid_from':_utc(spec['contract']['valid_from']),'valid_until':_utc(spec['contract']['valid_until'])})
    hours=CertifiedMarketHoursRuntimeProviderV2(calendar_snapshot=CertifiedCalendarSnapshotV2(
        frozenset(date.fromisoformat(d) for d in spec['covered_dates']),
        frozenset(date.fromisoformat(d) for d in spec['closed_dates'])),
        special_hours_snapshot=CertifiedSpecialHoursSnapshotV2(tuple(CertifiedSpecialHoursWindowV2(
            date.fromisoformat(w['date']),wall_time.fromisoformat(w['open']),wall_time.fromisoformat(w['close']))
            for w in spec['special_hours'])))
    return CurrentCandleAuthorityV1(contract=contract,market_hours=hours,
        maximum_age_seconds=settings.maximum_quote_age_seconds,clock=clock)


def validate_runway(gate, now, seconds):
    context=ordinary_calendar_context(gate.market_hours,now)
    if (not gate.contract.valid_from<=now<=now+timedelta(seconds=seconds)<gate.contract.valid_until
            or context['state']!='OPEN' or not context['next_boundary']
            or now+timedelta(seconds=seconds)>=_utc(context['next_boundary'])):
        raise ValueError('BOUNDED_ORDINARY_OPEN_WINDOW_REQUIRED')


def fresh_candidate(directory, existing):
    candidates=[p for p in set(directory.glob('*.jsonl'))-existing if p.name.count('.')==1]
    if len(candidates)>1:
        raise ValueError('AMBIGUOUS_FRESH_SESSIONS')
    if not candidates or not candidates[0].stat().st_size:
        return None
    path=candidates[0]
    UUID(path.stem)
    return path


def write_new(path, value):
    with Path(path).open('x',encoding='utf-8') as output:
        json.dump(value,output,indent=2,allow_nan=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',required=True)
    parser.add_argument('--directory',required=True)
    parser.add_argument('--run-directory',required=True,help='Must not exist')
    parser.add_argument('--seconds',type=int,default=7500)
    parser.add_argument('--activation-seconds',type=int,default=180)
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--risk-profile',help='Explicit operator-approved private risk environment JSON')
    parser.add_argument('--enable-local-paper',action='store_true')
    parser.add_argument('--preflight-only',action='store_true')
    args=parser.parse_args(argv)
    op=server=worker=sock=None
    created=False
    run=Path(args.run_directory)
    clock=lambda:datetime.now(timezone.utc)
    try:
        if not 30<=args.seconds<=10800 or not 30<=args.activation_seconds<=600 or not 1024<=args.port<=65535:
            raise ValueError('BOUNDED_ARGUMENTS_REQUIRED')
        if run.exists():
            raise ValueError('FRESH_NAMESPACE_REQUIRED')
        directory=Path(args.directory)
        if not directory.is_dir():
            raise ValueError('EVIDENCE_DIRECTORY_REQUIRED')
        if args.risk_profile:
            profile=read_json(args.risk_profile)
            if set(profile)!=RISK_KEYS or any(type(v) is not str for v in profile.values()):
                raise ValueError('EXPLICIT_RISK_PROFILE_REQUIRED')
            os.environ.update(profile)
        settings=APISettings()  # Missing or invalid policy fails before watcher activation.
        config=PaperResearchConfigV1.load('backend/config/paper_research_sprint07r.json')
        spec=review(args.spec,clock())
        gate=make_authorities(spec,settings,clock)
        validate_runway(gate,clock(),args.seconds+args.activation_seconds)
        news_path=settings.certified_economic_news_path
        news=EconomicNewsRuntimeProviderV2(snapshot=CertifiedEconomicNewsSnapshotLoaderV2().load_from_file(
            file_path=news_path) if news_path else None)
        # Required sources are pinned and rechecked throughout the run.
        spec_bytes=Path(args.spec).read_bytes()
        news_bytes=Path(news_path).read_bytes() if news_path else None

        def calendar_check(now):
            if Path(args.spec).read_bytes()!=spec_bytes or review(args.spec,now)!=spec:
                raise ValueError('CALENDAR_CHANGED')
            validate_runway(gate,now,0)
            if news_path and Path(news_path).read_bytes()!=news_bytes:
                raise ValueError('NEWS_AUTHORITY_CHANGED')

        # Bind before publishing WAITING; a conflicting service cannot masquerade
        # as this run's dashboard. No network broker/client is constructed.
        sock=socket.socket()
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        sock.bind(('127.0.0.1',args.port))
        sock.listen(128)
        if args.preflight_only:
            print(json.dumps(dict(status='PREFLIGHT_PASS',execution_mode='LOCAL_PAPER',
                news_status='CERTIFIED_COVERAGE' if news.is_timestamp_covered(timestamp=clock()) else 'NEWS_UNCERTIFIED_ENTRIES_BLOCKED',
                local_entry_intent=args.enable_local_paper,broker_order_calls=0,live_authority=False)))
            return
        run.mkdir(parents=True,exist_ok=False)
        created=True
        existing=set(directory.glob('*.jsonl'))
        armed=clock()
        identity=str(uuid4())
        write_new(run/'waiting.json',dict(schema='arms.local-paper-watcher.v1',watcher_id=identity,
            status='WAITING_FOR_FRESH_NATIVE_SESSION',pid=os.getpid(),armed_at=armed.isoformat(),
            activation_deadline=(armed+timedelta(seconds=args.activation_seconds)).isoformat(),
            excluded_files=sorted(p.name for p in existing),capture_seconds=args.seconds,
            execution_mode='LOCAL_PAPER',broker_order_calls=0))
        print('ACTIVE_AND_WAITING WAITING_FOR_FRESH_NATIVE_SESSION',flush=True)
        deadline=time.monotonic()+args.activation_seconds
        market=None
        while time.monotonic()<deadline:
            calendar_check(clock())
            market=fresh_candidate(directory,existing)
            if market: break
            time.sleep(.25)  # Delivery scheduling only; never repairs timestamps.
        if market is None:
            raise ValueError('ACTIVATION_EXPIRED')
        validation=CurrentPaperServiceV1(gate=gate,config=config,settings=settings,
            state_path=run/'validation.sqlite',initialization_policy='NEW_ISOLATED_PAPER_ACCOUNT')
        op=OperationalPaperV1(validation_service=validation,path=market,provider=spec['provider_enum'],
            expiry=spec['expiry'],config=config,settings=settings,state_path=run/'paper.sqlite',
            calendar_check=calendar_check,news_provider=news,enable_local_paper=args.enable_local_paper)
        # Before processing any candle, require the first HELLO to belong to a
        # fresh UUID created after arming. Incomplete evidence fails closed.
        with market.open('rb') as stream:
            first=stream.readline(16385)
        if not first.endswith(b'\n'):
            raise ValueError('INCOMPLETE_FRESH_HELLO')
        hello=json.loads(first,object_pairs_hook=_object)
        if hello.get('kind')!='HELLO' or hello.get('session')!=market.stem or _utc(hello['event_time'])<armed:
            raise ValueError('FRESH_HELLO_REQUIRED')
        op.poll()
        from backend.api.operational_paper_app_v1 import create_operational_paper_app_v1
        import uvicorn
        server=uvicorn.Server(uvicorn.Config(create_operational_paper_app_v1(runtime=op),
            host='127.0.0.1',port=args.port,access_log=False,log_level='error'))
        worker=Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True)
        worker.start()
        write_new(run/'active.json',dict(status='CONSUMING_FRESH_NATIVE_SESSION',watcher_id=identity,
            native_session=market.stem,started_at=clock().isoformat(),api_port=args.port))
        deadline=time.monotonic()+args.seconds
        while time.monotonic()<deadline:
            if not worker.is_alive(): raise ValueError('DASHBOARD_HOST_STOPPED')
            op.poll()
            time.sleep(.25)
        op.enabled=False
        if op.runtime is not None: op.runtime.control('disable')
        report=op.report()
        report.update(watcher_id=identity,native_session=market.stem,ended_at=clock().isoformat(),
            bound_seconds=args.seconds,open_positions_at_end=len(op.get_snapshot().get('active_simulated_positions') or []),
            end_policy='STOP_NO_FORCED_EXIT_NO_AUTOMATIC_RESUME')
        write_new(run/'report.json',report)
        print('BOUNDED_LOCAL_PAPER_OBSERVATION_COMPLETE',flush=True)
    except (Exception,KeyboardInterrupt):
        # No provider-owned strings, environment, personal paths or secrets.
        if created and not (run/'failure.json').exists():
            failure=dict(status='FAIL_CLOSED_REVIEW_REQUIRED',broker_order_calls=0,live_authority=False)
            if op is not None:
                op.fault='OPERATIONAL_PAPER_RECOVERY_REQUIRED'
                try: failure['observation']=op.report()
                except Exception: failure['observation']='REPORT_UNAVAILABLE_RECOVERY_REQUIRED'
            try: write_new(run/'failure.json',failure)
            except Exception: print('FAILURE_REPORT_UNAVAILABLE',flush=True)
        print('FAIL_CLOSED_REVIEW_REQUIRED',flush=True)
        raise SystemExit(1) from None
    finally:
        clean=True
        if server is not None: server.should_exit=True
        try:
            if worker is not None: worker.join(timeout=5)
        except Exception: clean=False
        try:
            if op is not None: op.close()
        except Exception: clean=False
        try:
            if sock is not None: sock.close()
        except Exception: clean=False
        if created:
            try: write_new(run/'cleanup.json',dict(status='PASS' if clean else 'FAILED_REVIEW_REQUIRED',
                automatic_resume=False,forced_exit=False,broker_order_calls=0))
            except Exception: clean=False
        if not clean:
            print('CLEANUP_FAILED_REVIEW_REQUIRED',flush=True)
            raise SystemExit(1) from None


if __name__=='__main__':
    main()
