"""Explicit local PAPER consumer of the unchanged certified native admission path.

The source reader retains its disabled validation namespace. Its admitted canonical
observations feed one separate operational account using the existing runtime.
No native account, network broker, order routing or alternative pricing logic.
"""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from threading import RLock

from backend.backtesting.current_paper_runtime_v1 import CurrentPaperServiceV1, _CurrentRuntimeV1
from backend.market_data.ninjatrader_market_reader_v1 import NinjaTraderMarketReaderV1, _utc
from backend.market_data.native_certification_v1 import certify_startup
from backend.market_data.sim_binding_contract_v1 import native_sim_status
from backend.services.economic_news_runtime_provider_v2 import EconomicNewsRuntimeProviderV2


def _public(value):
    if isinstance(value, dict):
        return {k:_public(v) for k,v in value.items()
                if k not in {'account','account_id','account_name','broker_position_id','fault_detail'}}
    if isinstance(value, list):
        return [_public(v) for v in value]
    return value


class _AdmittedReader(NinjaTraderMarketReaderV1):
    def _frame(self, raw):
        super()._frame(raw)  # Frozen parser, metadata, chronology, freshness and candle authority.
        self.owner._accepted_frame(json.loads(raw))


class OperationalPaperV1:
    def __init__(self, *, validation_service, path, provider, expiry, config, settings,
                 state_path, calendar_check, news_provider, enable_local_paper=False):
        if type(validation_service) is not CurrentPaperServiceV1:
            raise TypeError("canonical validation service required")
        if type(news_provider) is not EconomicNewsRuntimeProviderV2 or not callable(calendar_check):
            raise TypeError("explicit calendar and news authorities required")
        if type(enable_local_paper) is not bool:
            raise TypeError("explicit local entry intent required")
        if Path(state_path).exists():
            raise ValueError("RECOVERY_REQUIRED_EXISTING_OPERATIONAL_NAMESPACE")
        self._lock = RLock()
        self.validation = validation_service
        self.gate = validation_service.gate
        self.reader = _AdmittedReader(service=validation_service,path=path,provider=provider,expiry=expiry)
        self.reader.owner = self
        self._arguments = dict(gate=self.gate, mode="PAPER_RESEARCH",config=config,settings=settings,
            policy=self.gate,contract=self.gate.contract.contract,state_path=state_path,
            initialization_policy="NEW_ISOLATED_PAPER_ACCOUNT")
        self.calendar_check, self.news = calendar_check, news_provider
        self.enabled = enable_local_paper
        self.runtime = None
        self.fault = None
        self.stopped = False
        self.startup = "PENDING"
        self.started_at = self.gate.clock()
        self.last_count = 0
        self.frames, self.decisions = Counter(), Counter()
        self.decision_records = []
        self.max_drawdown = 0.0
        self.news_blocks = 0
        self.poll_failures = 0
        self.hello_time = None

    def _news_status(self, timestamp):
        if not self.news.is_timestamp_covered(timestamp=timestamp):
            return "NEWS_UNCERTIFIED"
        if self.news.get_economic_news_authority().is_news_blocked(symbol="NQ",timestamp=timestamp):
            return "NEWS_BLOCKED"
        return "CLEAR"

    def _accepted_frame(self, frame):
        self.frames[frame['kind']] += 1
        if frame['kind'] == 'HELLO':
            self.hello_time = _utc(frame['event_time'])
            result = certify_startup(self.reader.path.with_suffix('.connection.jsonl'),
                self.reader.session,_utc(frame['event_time']),self.reader.provider)
            self.startup = result['status']
        if frame['kind'] != 'CLOSED':
            return
        if self.startup != 'PASS' or self.gate.closed_count != self.last_count+1:
            raise ValueError("UNPROVEN_CANONICAL_DELIVERY")
        check = self.validation.get_snapshot()
        if check.get('active_simulated_positions') or check.get('completed_trades'):
            raise ValueError("VALIDATION_NAMESPACE_EXECUTION")
        row = self.validation._runtime._paper.runtime.current
        if row.available_at != self.gate.last_closed:
            raise ValueError("CANONICAL_OBSERVATION_MISMATCH")
        self.calendar_check(self.gate.clock())
        if self.runtime is None:
            self.runtime = _CurrentRuntimeV1(observations=(row,),**self._arguments)
        # News veto blocks new entries only; proven fresh candles retain canonical
        # SL/TP/marking of an already authorized local position.
        news = self._news_status(row.available_at)
        if news == 'CLEAR':
            news = self._news_status(self.gate.clock())
        self.news_blocks += int(news != 'CLEAR')
        db = self.runtime._db
        db.execute('CREATE TABLE IF NOT EXISTS operational_decisions (source_event_id TEXT PRIMARY KEY, phase TEXT NOT NULL, payload TEXT NOT NULL)')
        db.execute('INSERT INTO operational_decisions VALUES (?, ?, ?)',
            (row.event_id, 'INFLIGHT', json.dumps(dict(canonical_time=row.available_at.isoformat(), news_status=news))))
        db.commit()  # Trace uncertainty precedes PAPER mutation; restart never resumes.
        self.runtime.control('enable' if self.enabled and news == 'CLEAR' else 'disable')
        self.runtime._paper.runtime.pending = row
        self.runtime.ingest(row,received_at=row.received_at)
        self.last_count += 1
        snap = self.runtime.get_snapshot()
        decision = snap.get('latest_decision')
        if decision is not None:
            self.decisions[decision['action']] += 1
        else:
            self.decisions['NOT_EVALUATED'] += 1
        submission = snap.get('submission') or {}
        record = dict(canonical_time=row.available_at.isoformat(),source_event_id=row.event_id,
            decision=decision,risk=snap.get('risk_evaluation',[]),
            accepted=submission.get('accepted') is True,news_status=news,
            block_reasons=snap.get('readiness_reasons',[]),
            plan=snap.get('plan'),position_id=(submission.get('position') or {}).get('position_id'))
        # The core runtime atomically commits account/event/journal. This trace is
        # a separate completion checkpoint; uncertainty remains INFLIGHT on failure.
        db.execute("UPDATE operational_decisions SET phase='COMPLETED', payload=? WHERE source_event_id=?",
            (json.dumps(record,sort_keys=True,allow_nan=False),row.event_id))
        db.commit()
        self.decision_records.append(record)
        del self.decision_records[:-50]
        self.max_drawdown=max(self.max_drawdown,float(snap['account_overview']['drawdown']))
        if any(self.reconcile().values()):
            raise ValueError('PAPER_RECONCILIATION_FAILED')

    def reconcile(self):
        if self.runtime is None:
            return dict(duplicate_execution=0,duplicate_pnl=0,account_drift=0,journal_mismatch=0,unexplained_differences=0)
        r = self.runtime._paper.runtime
        state = r.account.get_state()
        trades = r.completed
        ids = [t['position_id'] for t in trades]
        net = sum(t['net_pnl'] for t in trades)
        journal = self.runtime._db.execute('SELECT payload FROM journal').fetchall()
        durable = [json.loads(row[0]) for row in journal]
        drift = abs(state['realized_pnl']-net)>1e-7 or abs(state['balance']-state['starting_balance']-net)>1e-7
        mismatch = sorted(durable,key=lambda t:t['position_id']) != sorted(trades,key=lambda t:t['position_id'])
        duplicate = len(ids)-len(set(ids))
        fills = r.lifecycle.broker_connector_v2.get_fills()  # Existing in-memory PAPER connector only.
        fill_ids = [f['order_id'] for f in fills]
        duplicate_entry = len(fill_ids)-len(set(fill_ids))
        open_ids = {p['position_id'] for p in r.lifecycle.get_active_positions()}
        unrealized = sum(p['unrealized_pnl'] for p in r.lifecycle.get_active_positions())
        daily = sum(t['net_pnl'] for t in trades if t['trading_date']==state['trading_day'])
        drift |= abs(state['daily_pnl']-daily)>1e-7 or abs(state['unrealized_pnl']-unrealized)>1e-7
        drift |= abs(state['equity']-state['balance']-unrealized)>1e-7
        mismatch |= set(r.entries) != set(ids) | open_ids or len(fills) != len(r.entries)
        mismatch |= bool(set(ids) & open_ids) or state['open_positions'] != len(open_ids)
        traces = self.runtime._db.execute("SELECT payload FROM operational_decisions WHERE phase='COMPLETED'").fetchall()
        accepted = [json.loads(t[0])['position_id'] for t in traces if json.loads(t[0])['accepted']]
        mismatch |= len(accepted) != len(r.entries) or set(accepted) != set(r.entries)
        mismatch |= len(traces) != self.last_count or bool(self.runtime._db.execute(
            "SELECT count(*) FROM operational_decisions WHERE phase!='COMPLETED'").fetchone()[0])
        mismatch |= {t.position_id for t in r.journal.trades} != set(r.entries)
        mismatch |= state['closed_positions'] != len(trades)
        return dict(duplicate_execution=duplicate_entry,duplicate_pnl=duplicate,
            account_drift=int(drift),journal_mismatch=int(mismatch),
            unexplained_differences=int(bool(drift or mismatch or duplicate or duplicate_entry)))

    def poll(self):
        with self._lock:
            if self.fault or self.stopped:
                raise RuntimeError('STOPPED_OR_RECOVERY_REQUIRED')
            try:
                self.calendar_check(self.gate.clock())
                if self.hello_time is not None:
                    certify_startup(self.reader.path.with_suffix('.connection.jsonl'),
                        self.reader.session,self.hello_time,self.reader.provider)
                self.reader.poll()
            except Exception:
                self.poll_failures += 1
                self.fault = 'OPERATIONAL_PAPER_RECOVERY_REQUIRED'
                self.gate.connected = False
                if self.runtime is not None and not self.runtime._fault:
                    try:
                        self.runtime.control('disable')
                    except Exception:
                        pass  # Runtime has its own durable fail-closed latch.
                raise ValueError(self.fault) from None
            return self.get_snapshot()

    def get_snapshot(self):
        with self._lock:
            source = NinjaTraderMarketReaderV1.get_snapshot(self.reader)
            paper = self.runtime.get_snapshot() if self.runtime else {}
            reasons = list(paper.get('readiness_reasons',['AWAITING_MARKET_DATA']))
            reasons += self.gate.reasons()
            if not self.enabled: reasons.append('PAPER_DISABLED')
            if self.startup != 'PASS': reasons.append('STARTUP_UNPROVEN')
            if not source['provider_transport']['connected']: reasons.append('PROVIDER_NOT_CONNECTED')
            if self.fault: reasons.append(self.fault)
            if self.stopped: reasons.append('STOPPED')
            news = self._news_status(self.gate.clock())
            if news != 'CLEAR': reasons.append(news)
            # Publish only known local-account/strategy fields, never raw error,
            # native object, path, environment, credential or private spec.
            keys=('account_overview','active_simulated_positions','latest_decision','strategy_evidence',
                'risk_evaluation','plan','submission','execution_state','latest_canonical_trade',
                'completed_trades','journal_completed','journal_total','configuration','config_hash',
                'effective_policy','timeframe_readiness','htf_emitted','canonical_time','risk_vetoes')
            result={k:paper.get(k) for k in keys}
            for k in ('market_data','session_state','provider_state','data_freshness','provider_transport'):
                result[k]=source[k]
            for k in ('feed_contract_sha256','htf_current_session'):
                result[k]=source.get(k)
            result.update(mode='CURRENT_MARKET_PAPER',execution_mode='LOCAL_PAPER',
                execution_kind='SIMULATED / PAPER',config_hash=paper.get('config_hash',self.gate.digest),
                paper_ready=not reasons,dashboard_status='PAPER_READY' if not reasons else 'BLOCKED',
                readiness_reasons=list(dict.fromkeys(reasons)),news_status=news,startup_status=self.startup,
                canonical_timeframe='1m',
                journal_status='REVIEW_REQUIRED' if self.fault or self.gate.fault else (
                    'RECONCILED' if self.last_count else 'NOT_EVALUATED'),
                local_account_status='RECOVERY_REQUIRED' if self.fault or self.gate.fault else (
                    'AVAILABLE' if self.runtime else 'AWAITING_MARKET_DATA'),
                live_execution_allowed=False,live_authority=False,
                ninjatrader_account_access=False,broker_order_calls=0,
                recovery_required=bool(self.fault or self.gate.fault),
                latest_decision_trace=self.decision_records[-1] if self.decision_records else None,
                evidence_status='SYNTHETIC_OFFLINE' if self.gate.contract.fixture else 'NATIVE_CURRENT',
                **native_sim_status())
            return _public(deepcopy(result))

    def report(self):
        with self._lock:
            snap=self.get_snapshot()
            trades=self.runtime._paper.runtime.completed if self.runtime else []
            opened=len(self.runtime._paper.runtime.entries) if self.runtime else 0
            return dict(schema='arms.local-paper-soak.v1',execution_mode='LOCAL_PAPER',
                evidence_kind='SYNTHETIC_OFFLINE' if self.gate.contract.fixture else 'NATIVE_CURRENT',
                status='FAIL_CLOSED' if self.fault else 'BOUNDED_LOCAL_PAPER_OBSERVATION',
                runtime_duration_seconds=(self.gate.clock()-self.started_at).total_seconds(),
                canonical_candles=self.last_count,frame_counts=dict(self.frames),
                decisions=sum(v for k,v in self.decisions.items() if k!='NOT_EVALUATED'),
                buy_count=self.decisions['BUY'],sell_count=self.decisions['SELL'],
                hold_count=self.decisions['HOLD'],not_evaluated_count=self.decisions['NOT_EVALUATED'],
                paper_trades_opened=opened,paper_trades_closed=len(trades),
                wins=sum(t['net_pnl']>0 for t in trades),losses=sum(t['net_pnl']<0 for t in trades),
                gross_pnl=sum(t['gross_pnl'] for t in trades),net_pnl=sum(t['net_pnl'] for t in trades),
                max_drawdown=self.max_drawdown,risk_blocks=snap.get('risk_vetoes') or 0,
                news_blocks=self.news_blocks,duplicate_suppression=self.gate.duplicate_count,
                transport_or_freshness_failures=self.poll_failures,
                candle_gate_fault=self.gate.fault,transport_fault=self.reader.fault,
                last_native_sequence=self.reader.sequence,
                restart_recovery='NO_AUTOMATIC_RESUME_EXISTING_NAMESPACE_REJECTED',
                reconciliation=self.reconcile(),final_snapshot=snap,
                broker_order_calls=0,sim_execution_authority='DISABLED',live_authority=False)

    def close(self):
        with self._lock:
            if self.stopped: return
            self.stopped=True
            try:
                if self.runtime is not None: self.runtime.shutdown()
            finally:
                self.reader.close()
