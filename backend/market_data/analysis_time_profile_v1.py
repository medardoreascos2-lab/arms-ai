"""Source-relative observations only. No current-market admission or execution.

Explicit in-process input; never opens a feed, account, service or network socket.
The owner must establish a fresh same-host QPC epoch before native activation.
Unknown absolute/source recency and current-session authority never auto-promote.
"""
from collections import deque
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
from math import isfinite
from threading import RLock
from types import SimpleNamespace
from uuid import UUID

from backend.backtesting.closed_bar_aggregator_v1 import ClosedBarAggregatorV1
from backend.models.candle import Candle
from backend.smart_money.market_structure import MarketStructureEngine
from backend.smart_money.liquidity_engine import LiquidityEngine
from backend.smart_money.smart_money_engine_v2 import SmartMoneyEngineV2
from backend.trend.trend_engine_v2 import TrendEngineV2
from tools.native_timing_witness_v1 import IDENTITY, check_pair, ticks, MINUTE
from tools.production_timing_v1 import PAIR_FIELDS, parse


SCHEMA = 'arms.market-analysis-time-profile.v1'
EXPORTER_SHA256 = '9383d39f8b39f62d5bed235d69f4200e0a31d5a14515e5caf078805d03fcd350'
COMPONENTS = ('1m','15m','1h','trend','structure','liquidity','fvg','regime','confluence','confidence')


def require(value, reason):
    if not value:
        raise ValueError(reason)


class MarketAnalysisTimeProfileV1:
    def __init__(self, *, session, epoch, frequency, reader_start_qpc, qpc_clock,
                 heartbeat_seconds, maximum_processing_seconds, exporter_sha256,
                 calendar_evidence=None):
        require(str(UUID(session)) == session and isinstance(epoch,str) and bool(epoch), 'IDENTITY')
        require(type(frequency) is int and frequency > 0 and type(reader_start_qpc) is int
                and reader_start_qpc >= 0 and callable(qpc_clock), 'QPC_CONTEXT')
        require(exporter_sha256 == EXPORTER_SHA256, 'UNREVIEWED_EXPORTER')
        require(all(type(v) in (int,float) and isfinite(v) and v > 0
                    for v in (heartbeat_seconds,maximum_processing_seconds)), 'EXPLICIT_AGE_BUDGETS')
        self.session,self.epoch,self.frequency = session,epoch,frequency
        self.start = self.last_now = reader_start_qpc
        self.clock = qpc_clock
        self.heartbeat = heartbeat_seconds*frequency
        self.maximum_processing = maximum_processing_seconds*frequency
        self._lock = RLock()
        self.fault = None
        self.sequence = self.pair_sequence = -1
        self.last_receipt = self.last_emission = None
        self.previous_pair = self.forming = self.pending = None
        self.forming_count = 0
        self.candles = deque(maxlen=120)
        self.htf = ClosedBarAggregatorV1(history_limit=50)
        self.values = {}
        self.calendar_status = 'UNKNOWN'
        if calendar_evidence is not None:
            # An old calendar proof is not continuous binding of this new stream.
            from backend.market_data.loaded_calendar_binding_v1 import compare_loaded_calendar, NATIVE_SHA256
            native,template = calendar_evidence
            require(sha256(native).hexdigest() == NATIVE_SHA256, 'CALENDAR_BINDING_INVALID')
            compare_loaded_calendar(parse(native),template)
            self.calendar_status = 'REVIEWED_SNAPSHOT_ONLY'

    def _now(self):
        try:
            epoch,frequency,qpc = self.clock()
        except Exception:
            raise ValueError('QPC_UNAVAILABLE') from None
        require(epoch == self.epoch and frequency == self.frequency and type(qpc) is int
                and qpc >= self.last_now, 'QPC_EPOCH_OR_REGRESSION')
        self.last_now = qpc
        if self.last_receipt is not None:
            require(qpc-self.last_receipt <= self.heartbeat, 'TRANSPORT_LOSS')
        if self.last_emission is not None:
            require(qpc-self.last_emission <= self.maximum_processing, 'PROCESSING_AGE_EXPIRED')
        return qpc

    def revoke(self, reason='RESTART_OR_RECONNECT_REQUIRES_NEW_PROOF'):
        with self._lock:
            self.fault = self.fault or reason

    def accept(self, canonical_raw, timing_raw=None, *, receipt_qpc):
        """Explicit delivery by a future reviewed adapter, not a public API input.

        A frame with a sidecar is committed atomically. CLOSED stays pending until
        its same-callback FORMING record is verified. No synthetic seal or rows.
        """
        with self._lock:
            if self.fault:
                raise ValueError(self.fault)
            try:
                now = self._now()
                require(type(receipt_qpc) is int and self.start <= receipt_qpc <= now
                        and (self.last_receipt is None or receipt_qpc >= self.last_receipt), 'RECEIPT_ORDER')
                require(now-receipt_qpc <= self.maximum_processing, 'PROCESSING_DELAY')
                require(type(canonical_raw) is bytes and 0 < len(canonical_raw) <= 16384
                        and b'\n' not in canonical_raw and b'\r' not in canonical_raw, 'FRAME_SIZE_OR_LINES')
                row = parse(canonical_raw)
                require(set(row)==set('schema session sequence event_time kind payload'.split())
                        and row['schema']=='arms.nt.market.v1' and row['session']==self.session
                        and type(row['sequence']) is int and row['sequence']==self.sequence+1, 'SEQUENCE_OR_IDENTITY')
                ticks(row['event_time'])  # Syntax only; no fabricated absolute accuracy.
                kind,p = row['kind'],row['payload']
                if self.sequence < 0:
                    expected = dict(provider='Provider31',contract='NQ DEC26',expiry='2026-12-01',instrument='NQ',
                                    tick_size=.25,point_value=20,timeframe='1m',trading_hours_template='CME US Index Futures ETH',
                                    source_timezone='UTC',bar_label='CLOSE',realtime=True,read_only=True)
                    require(kind=='HELLO' and p==expected and p['realtime'] is True and p['read_only'] is True
                            and timing_raw is None, 'HELLO_IDENTITY')
                elif kind == 'HEARTBEAT':
                    require(p=={'connected':True} and p['connected'] is True and timing_raw is None
                            and self.pending is None, 'HEARTBEAT_STATE')
                elif kind in ('FORMING','CLOSED'):
                    self._bar(row,canonical_raw,timing_raw,receipt_qpc,now)
                else:
                    raise ValueError('TRANSPORT_TERMINATED')
                self.sequence,self.last_receipt = row['sequence'],receipt_qpc
            except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as error:
                self.fault = str(error) if type(error) is ValueError else 'MALFORMED_INPUT'
                raise ValueError(self.fault) from None

    def _bar(self,row,raw,paired,receipt,now):
        require(type(paired) is bytes and 0 < len(paired) <= 16384, 'TIMING_PAIR_REQUIRED')
        p=parse(paired); v=row['payload']; kind=row['kind']
        require(set(p)==PAIR_FIELDS and p['schema']=='arms.nt.production-timing.v1', 'PAIR_SCHEMA')
        require(all(type(p[k]) is int for k in ('pair_sequence','canonical_sequence','qpc_frequency',
                'callback_index','bar_index','bars_ago','bars_in_progress','bars_value')), 'PAIR_INTEGER')
        require(p['session']==self.session and p['canonical_sequence']==row['sequence']
                and p['pair_sequence']==self.pair_sequence+1 and p['canonical_sha256']==sha256(raw).hexdigest()
                and p['kind']==kind and p['qpc_frequency']==self.frequency, 'PAIR_BINDING')
        require(all(p[k]==v for k,v in IDENTITY.items()) and p['state']=='Realtime' and p['bars_in_progress']==0
                and p['first_tick'] is True and p['observation_only'] is True and p['runtime_admission'] is False, 'CALLBACK_PROVENANCE')
        cb,em=p['callback'],p['emission'];check_pair(cb);check_pair(em)
        require(self.start <= cb['qpc_before'] <= cb['qpc_after'] <= em['qpc_before'] <= em['qpc_after'] <= receipt
                and em['utc']==row['event_time'], 'PAIR_ORDER_OR_OLD_CAPTURE')
        require(now-em['qpc_before'] <= self.maximum_processing, 'TRANSPORT_PROCESSING_DELAY')
        if self.previous_pair:
            prev=self.previous_pair
            require(prev['emission']['qpc_after'] <= em['qpc_before'], 'EMISSION_REGRESSION')
            if prev['callback']!=cb:
                require(prev['emission']['qpc_after'] <= cb['qpc_before'], 'CALLBACK_REGRESSION')
        require(set(v)==set('bar_time open high low close volume'.split()), 'CANDLE_SCHEMA')
        require(all(type(v[k]) in (int,float) and isfinite(v[k]) and v[k]>0 and v[k]*4==int(v[k]*4)
                    for k in ('open','high','low','close')) and type(v['volume']) is int and v['volume']>=0
                and v['low']<=min(v['open'],v['close'])<=max(v['open'],v['close'])<=v['high'], 'OHLCV')
        label=ticks(v['bar_time'])
        require(label%MINUTE==0 and p['source_bar_label']==v['bar_time'] and p['bar_index']>=0
                and p['bar_index']==p['callback_index']-p['bars_ago'], 'BAR_LABEL')
        if kind=='CLOSED':
            require(self.pending is None and self.forming_count>=2 and p['bars_ago']==1
                    and self.forming['bar_index']==p['bar_index'] and self.forming['source_bar_label']==p['source_bar_label'], 'CLOSED_PROVENANCE')
            self.pending=(deepcopy(p),deepcopy(v))
        else:
            require(p['bars_ago']==0 and ((self.forming_count>=2)==(self.pending is not None)), 'MISSING_CLOSED')
            if self.forming:
                require(p['bar_index']==self.forming['bar_index']+1
                        and label==ticks(self.forming['source_bar_label'])+MINUTE, 'CANONICAL_GAP')
            if self.pending:
                closed,vclosed=self.pending
                require(closed['callback']==cb and closed['callback_index']==p['callback_index'], 'SAME_CALLBACK')
                candle=Candle('NQ','1m',*[vclosed[k] for k in ('open','high','low','close','volume')],
                              datetime.fromisoformat(vclosed['bar_time'].replace('Z','+00:00'))-timedelta(minutes=1))
                self.htf.update_completed(candle)
                self.candles.append(candle)
                self._compute()
            self.pending=None;self.forming=deepcopy(p);self.forming_count+=1
        self.pair_sequence=p['pair_sequence'];self.previous_pair=deepcopy(p);self.last_emission=em['qpc_before']

    def _compute(self):
        bars=list(self.candles)
        self.values={'1m':dict(close=bars[-1].close,source_open=bars[-1].timestamp.isoformat())}
        for timeframe in ('15m','1h'):
            h=self.htf.history(timeframe)
            if h:self.values[timeframe]=dict(close=h[-1].close,source_open=h[-1].timestamp.isoformat())
        if len(bars)>=50:
            store=SimpleNamespace(get_latest=lambda **kw: bars[-kw['limit']:])
            trend=TrendEngineV2(live_candle_store=store).analyze(symbol='NQ',timeframe='1m')
            self.values['trend']={k:trend[k] for k in ('direction','fast_ema','slow_ema','slope')}
        if len(bars)>=3:
            self.values['structure']={'classification':MarketStructureEngine().analyze(bars)}
            args={f'{n}_{k}':getattr(bar,k) for n,bar in zip(('first','second','third'),bars[-3:]) for k in ('high','low')}
            self.values['fvg']=SmartMoneyEngineV2().detect_fvg(**args)
        if len(bars)>=4:
            engine=LiquidityEngine();engine.analyze(bars)
            self.values['liquidity']=dict(equal_highs=engine.equal_highs,equal_lows=engine.equal_lows,
                                         sweep=engine.sweep_detected,direction=engine.sweep_direction)

    def snapshot(self):
        with self._lock:
            try:now=self._now()
            except (ValueError,TypeError):self.fault=self.fault or 'TRANSPORT_OR_EPOCH_LOST';now=self.last_now
            age=None if self.last_emission is None else max(0,now-self.last_emission)/self.frequency
            active=(self.fault is None and self.pending is None and self.last_emission is not None
                    and now-self.last_emission <= self.maximum_processing)
            components={k:dict(status='SOURCE_RELATIVE_ONLY',value=deepcopy(self.values[k])) if active and k in self.values else
                        dict(status='BLOCKED' if self.fault else 'NOT_PROJECTED' if k in ('regime','confluence','confidence') else 'INSUFFICIENT_OR_STALE_DATA',value=None)
                        for k in COMPONENTS}
            return dict(schema=SCHEMA,profile='MARKET_ANALYSIS_TIME_PROFILE',
                market_stream='LIVE' if active else 'NOT_LIVE',stream_meaning='LOCAL_EXPORTER_OBSERVATIONS_NOT_ABSOLUTE_MARKET_RECENCY',
                transport_liveness='OBSERVED_RECEIPTS' if self.last_receipt is not None and not self.fault else 'UNKNOWN_OR_LOST',
                processing_age=dict(status='QPC_OBSERVED' if age is not None and not self.fault else 'UNKNOWN',seconds=age),
                canonical_continuity='CONTIGUOUS_OBSERVED' if active else 'UNPROVEN_OR_REVOKED',
                source_time_status='LABELS_AND_RELATIVE_PROGRESS_ONLY' if active else 'UNKNOWN',
                source_time_recency='UNKNOWN',absolute_market_recency='UNKNOWN',absolute_time_authority='UNKNOWN',
                session_authority='UNKNOWN',session_status='UNKNOWN',calendar_binding=self.calendar_status,news_authority='UNCERTIFIED',
                analysis_status='SOURCE_RELATIVE_ONLY' if active and self.candles else 'BLOCKED',
                decision_status='NOT_PROJECTED',components=components,data_freshness='NOT_ASSERTED',
                execution_mode='LOCAL_PAPER',paper_entry_authority='DISABLED',sim_execution_authority='DISABLED',live_authority=False,
                broker_order_calls=0,ninjatrader_account_access=False,paper_trades_opened=0,
                sequence=self.sequence,session=self.session,epoch=self.epoch,fault=self.fault)
