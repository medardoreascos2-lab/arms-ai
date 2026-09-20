"""Bounded one-session read-only certification harness. No broker dependency.

Run before adding the exporter. An explicit directory is watched for exactly
one new market file; companion files cannot grant market admission. Raw evidence
stays in place. Reports contain summaries/hashes, never account IDs or local paths.
"""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import json
from pathlib import Path
import time
from decimal import Decimal, InvalidOperation

from backend.market_data.ninjatrader_market_reader_v1 import NinjaTraderMarketReaderV1, _object, _utc


class NativeCertificationCaptureV1:
    def __init__(self, reader, *, purpose):
        if type(reader) is not NinjaTraderMarketReaderV1 or purpose not in {"market_open", "daily_boundary"}:
            raise ValueError("explicit canonical reader and capture purpose required")
        self.reader, self.purpose = reader, purpose
        self.states = []
        self.frames = Counter()
        self.frame_times = {}
        self.trace = []
        self.fault = None
        self._observed_sequence = -1
        self._digest = sha256()
        self._audit_file = None
        self._last_close = None
        self._baseline_account = None
        self.account_drift = False
        self.closed_heartbeats = 0

    def poll(self):
        try:
            snapshot = self.reader.poll()
            # Independently summarize only the exact frames already admitted by
            # the canonical live reader, never replay an old file with a fake clock.
            if self._audit_file is None:
                self._audit_file = self.reader.path.open("rb")
            while self._observed_sequence < self.reader.sequence:
                raw = self._audit_file.readline(16385)
                if not raw.endswith(b"\n") or len(raw) > 16384:
                    raise ValueError("capture integrity")
                f = json.loads(raw, object_pairs_hook=_object)
                if f["sequence"] != self._observed_sequence + 1 or f["session"] != self.reader.session:
                    raise ValueError("capture sequence")
                self._observed_sequence += 1
                if f["kind"] in {"CLOSED", "FORMING"}:
                    p = f["payload"]
                    try:
                        prices = [Decimal(str(p[k])) for k in ("open","high","low","close")]
                        if (any(not x.is_finite() or x <= 0 or x % Decimal(".25") for x in prices)
                                or not prices[2] <= min(prices[0],prices[3]) <= max(prices[0],prices[3]) <= prices[1]
                                or type(p["volume"]) is not int or p["volume"] < 0):
                            raise ValueError("invalid OHLCV")
                    except (InvalidOperation, TypeError):
                        raise ValueError("invalid OHLCV") from None
                self._digest.update(raw)
                self.frames[f["kind"]] += 1
                times = self.frame_times.setdefault(f["kind"], [f["event_time"], f["event_time"]])
                times[1] = f["event_time"]
                if f["kind"] == "CLOSED":
                    label = _utc(f["payload"]["bar_time"])
                    if self._last_close is not None and label <= self._last_close:
                        raise ValueError("duplicate canonical close")
                    self._last_close = label
                if f["kind"] == "HEARTBEAT":
                    from backend.market_data.session_state_v1 import SessionStateAuthorityV1
                    state_at_event = SessionStateAuthorityV1(self.reader.service.gate.market_hours).resolve(_utc(f["event_time"]))
                    if not state_at_event.scheduled_open and state_at_event.state != "UNKNOWN":
                        self.closed_heartbeats += 1
                if len(self.trace) >= 40000:
                    raise ValueError("capture record limit")
                self.trace.append(dict(sequence=f["sequence"], kind=f["kind"], event_time=f["event_time"],
                    bar_time=f["payload"].get("bar_time")))
            state = snapshot["session_state"]["state"]
            now = self.reader.service.gate.clock().isoformat()
            if not self.states or self.states[-1]["state"] != state:
                self.states.append(dict(state=state, observed_at=now,
                    last_closed=snapshot["market_data"]["last_closed_1m_time"],
                    provider=snapshot["provider_state"],htf=dict(snapshot.get("htf_emitted",{}))))
            account = snapshot.get("account_overview")
            if account is not None:
                values = tuple(account.get(k) for k in ("balance", "equity", "realized_pnl"))
                if self._baseline_account is None:
                    self._baseline_account = values
                self.account_drift |= values != self._baseline_account
            if (snapshot.get("completed_trades",0) or snapshot.get("journal_completed",0)
                    or snapshot.get("active_simulated_positions") or snapshot["external_order_authority"]):
                raise ValueError("execution invariant")
            return snapshot
        except Exception:
            self.fault = "CAPTURE_OR_TRANSPORT_RECOVERY_REQUIRED"
            self.reader.close()
            raise ValueError(self.fault) from None

    def report(self):
        snapshot = self.reader.get_snapshot()
        htf = snapshot.get("htf_emitted", {})
        closed = snapshot["market_data"]["closed_candles"]
        states = [s["state"] for s in self.states]
        boundary = False
        for i, state in enumerate(states):
            if state == "DAILY_MAINTENANCE" and "OPEN" in states[:i] and "REOPENING" in states[i+1:]:
                reopening = states.index("REOPENING", i+1)
                boundary = "OPEN" in states[reopening+1:]
        hb = self.frame_times.get("HEARTBEAT")
        heartbeat_span = (_utc(hb[1])-_utc(hb[0])).total_seconds() if hb else 0
        milestones = dict(forming_1m=self.frames["FORMING"] > 0, closed_1m=closed >= 2,
            htf_15m=htf.get("15m",0) > 0, htf_1h=htf.get("1h",0) > 0,
            strategy_evaluated=snapshot.get("latest_decision") is not None,
            transport_30_seconds=heartbeat_span >= 30,
            daily_boundary=boundary and self.closed_heartbeats >= 2)
        required = [v for k,v in milestones.items() if k != "daily_boundary" or self.purpose == "daily_boundary"]
        return dict(schema="arms.native-certification.v1", purpose=self.purpose,
            evidence_kind="SYNTHETIC_OFFLINE" if self.reader.service.gate.contract.fixture else "NATIVE_CURRENT",
            status="FAIL_CLOSED" if self.fault or self.account_drift or "UNKNOWN" in states else "PENDING_NATIVE_CERTIFICATION",
            observed_market_milestones_complete=all(required), milestones=milestones,
            session=self.reader.session, source_prefix_sha256=self._digest.hexdigest(),
            frame_counts=dict(self.frames), frame_times=self.frame_times, states=self.states, trace=self.trace,
            closed_session_heartbeats=self.closed_heartbeats, heartbeat_span_seconds=heartbeat_span,
            canonical_candles=closed, htf=htf, account_drift=int(self.account_drift),
            journal_completed=snapshot.get("journal_completed",0), completed_trades=snapshot.get("completed_trades",0),
            duplicate_canonical_candles=0 if not self.fault else "UNPROVEN",
            broker_order_calls=0, sim_execution_authority="DISABLED", live_authority=False,
            startup="PENDING_SIDECAR_VERIFICATION", first_raw_tick="NOT_EXPORTED_BY_PROTOCOL",
            stale_rejection="OFFLINE_TESTED_NOT_INJECTED_IN_NATIVE_STREAM", fault=self.fault)

    def close(self):
        if self._audit_file:
            self._audit_file.close()
        self.reader.close()


def certify_startup(sidecar, session, hello_time, provider):
    """Strict bounded sidecar audit; absence/contradiction never becomes PASS."""
    with Path(sidecar).open("rb") as source:
        raw = source.read(1_000_001)
    if len(raw) > 1_000_000 or not raw.endswith(b"\n"):
        raise ValueError("incomplete sidecar")
    rows = [json.loads(line, object_pairs_hook=_object) for line in raw.splitlines()]
    aligned = None
    previous = None
    for i, row in enumerate(rows):
        if row["schema"] != "arms.nt.connection-diagnostic.v1" or row.get("kind") != "CONNECTION_STATUS" or row["session"] != session or type(row["sequence"]) is not int or row["sequence"] != i:
            raise ValueError("sidecar identity")
        p = row["payload"]
        if any(p.get(k) is not True for k in ("same_source","source_present","callback_present","source_snapshot_stable")):
            raise ValueError("source unproven")
        if any(p.get(k) != "Connected" for k in ("source_price_status","source_connection_status","source_price_status_after","source_connection_status_after")):
            raise ValueError("source not connected")
        if p.get("callback_provider") != provider or p.get("source_provider") != provider:
            raise ValueError("provider mismatch")
        current = _utc(row["event_time"])
        received = _utc(row["callback_received_time"])
        if received > current or (previous is not None and current < previous):
            raise ValueError("sidecar time regressed")
        previous = current
        if p.get("decision") not in {"CONTINUE","WAIT_STARTUP_ALIGNMENT"}:
            raise ValueError("native revocation")
        prior_status = (p.get("callback_previous_price_status"), p.get("callback_previous_connection_status"))
        if any(s not in {"Disconnected","Connecting","Connected"} for s in prior_status):
            raise ValueError("prior continuity unknown or lost")
        if current > hello_time and (p["decision"] != "CONTINUE" or prior_status != ("Connected","Connected")):
            raise ValueError("post-admission continuity unproven")
        if _utc(row["event_time"]) <= hello_time and p["decision"] == "CONTINUE":
            if p["callback_price_status"] != "Connected" or p["callback_connection_status"] != "Connected":
                raise ValueError("alignment invalid")
            aligned = _utc(row["event_time"])
    if aligned is None or not 0 <= (hello_time-aligned).total_seconds() < 30:
        raise ValueError("startup unproven")
    return dict(status="PASS", sha256=sha256(raw).hexdigest(), records=len(rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="Private reviewed feed/calendar JSON; no accounts")
    parser.add_argument("--directory", required=True)
    parser.add_argument("--state", required=True, help="New private isolated SQLite path")
    parser.add_argument("--output", required=True, help="New private report path")
    parser.add_argument("--purpose", choices=("market_open","daily_boundary"), required=True)
    parser.add_argument("--seconds", type=int, default=7500)
    parser.add_argument("--activation-seconds", type=int, default=180)
    args = parser.parse_args()
    if not 30 <= args.seconds <= 10800 or not 30 <= args.activation_seconds <= 600:
        parser.error("bounded duration required")
    if Path(args.state).exists() or Path(args.output).exists():
        parser.error("new state and output required")
    from datetime import date, time as wall_time
    from backend.market_data.current_candle_authority_v1 import CurrentFeedContractV1, CurrentCandleAuthorityV1
    from backend.services.certified_market_calendar_v2 import CertifiedCalendarSnapshotV2
    from backend.services.certified_market_hours_runtime_provider_v2 import CertifiedMarketHoursRuntimeProviderV2
    from backend.services.special_hours_snapshot_v2 import CertifiedSpecialHoursSnapshotV2, CertifiedSpecialHoursWindowV2
    from backend.backtesting.current_paper_runtime_v1 import CurrentPaperServiceV1
    from backend.backtesting.paper_research_v1 import PaperResearchConfigV1
    from backend.config.api_settings import APISettings
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"), object_pairs_hook=_object)
    source = Path(spec["calendar_evidence_file"])
    if sha256(source.read_bytes()).hexdigest() != spec["calendar_evidence_sha256"]:
        parser.error("reviewed calendar evidence changed")
    contract = CurrentFeedContractV1(**{**spec["contract"], "valid_from":_utc(spec["contract"]["valid_from"]),
        "valid_until":_utc(spec["contract"]["valid_until"])})
    if contract.fixture:
        parser.error("native capture cannot use a fixture contract")
    hours = CertifiedMarketHoursRuntimeProviderV2(calendar_snapshot=CertifiedCalendarSnapshotV2(
        frozenset(date.fromisoformat(d) for d in spec["covered_dates"]),
        frozenset(date.fromisoformat(d) for d in spec["closed_dates"])),
        special_hours_snapshot=CertifiedSpecialHoursSnapshotV2(tuple(CertifiedSpecialHoursWindowV2(
            date.fromisoformat(w["date"]),wall_time.fromisoformat(w["open"]),wall_time.fromisoformat(w["close"])) for w in spec["special_hours"])))
    directory = Path(args.directory)
    existing = set(directory.glob("*.jsonl"))
    deadline = time.monotonic()+args.activation_seconds
    market = None
    while time.monotonic() < deadline:
        candidates = [p for p in set(directory.glob("*.jsonl"))-existing if p.name.count(".") == 1]
        if len(candidates) > 1:
            parser.error("multiple new sessions; review required")
        if candidates and candidates[0].stat().st_size:
            market = candidates[0]
            break
        time.sleep(.25)
    if market is None:
        parser.error("bounded activation window expired")
    settings = APISettings()
    gate = CurrentCandleAuthorityV1(contract=contract, market_hours=hours,
        maximum_age_seconds=settings.maximum_quote_age_seconds,clock=lambda:datetime.now(timezone.utc))
    service = CurrentPaperServiceV1(gate=gate,config=PaperResearchConfigV1.load("backend/config/paper_research_sprint07r.json"),
        settings=settings,state_path=args.state,initialization_policy="NEW_ISOLATED_PAPER_ACCOUNT")
    reader = NinjaTraderMarketReaderV1(service=service,path=market,provider=spec["provider_enum"],expiry=spec["expiry"])
    capture = NativeCertificationCaptureV1(reader,purpose=args.purpose)
    deadline = time.monotonic()+args.seconds
    try:
        while time.monotonic() < deadline:
            capture.poll()
            time.sleep(.25)
    except (ValueError, KeyboardInterrupt):
        capture.fault = capture.fault or "CAPTURE_INTERRUPTED"
    finally:
        report = capture.report()
        try:
            report["startup"] = certify_startup(market.with_suffix(".connection.jsonl"),reader.session,
                                                  _utc(capture.frame_times["HELLO"][0]), reader.provider)
            if report["status"] != "FAIL_CLOSED" and report["observed_market_milestones_complete"]:
                report["status"] = "PASS_BOUNDED_OBSERVATION_ONLY"
        except (ValueError, KeyError, OSError, TypeError):
            report["startup"] = "UNPROVEN"
            report["status"] = "FAIL_CLOSED"
        report["calendar_evidence_sha256"] = spec["calendar_evidence_sha256"]
        capture.close()
        with Path(args.output).open("x",encoding="utf-8") as output:
            json.dump(report,output,indent=2,allow_nan=False)
        print(report["status"])


if __name__ == "__main__":
    main()
