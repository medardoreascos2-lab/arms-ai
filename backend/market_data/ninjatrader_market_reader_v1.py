"""Private, one-way NinjaTrader JSONL admission. No account or order channel.

The file is trusted only as a local transport, never as candle certification.
The existing current candle authority still validates prices, time and calendar.
This first activation milestone always disables local PAPER entries as well.
"""
from datetime import datetime, timezone
import json
from math import isfinite
from pathlib import Path
from threading import RLock
from uuid import UUID

from backend.backtesting.current_paper_runtime_v1 import CurrentPaperServiceV1
from backend.market_data.current_candle_authority_v1 import CurrentMarketEventV1, instant


SCHEMA = "arms.nt.market.v1"
MAX_LINE = 16384


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("UTC timestamp required")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError("explicit UTC required")
    return instant(result)


class NinjaTraderMarketReaderV1:
    """One new file/session and isolated disabled service; restart needs review.

    No historical catch-up or rollover. Poll and snapshot share a lock. A stopped,
    replaced, truncated, stale or malformed stream latches recovery. GET snapshots
    do not poll, ingest or update positions.
    """
    def __init__(self, *, service, path, provider, expiry, heartbeat_seconds=15):
        if type(service) is not CurrentPaperServiceV1:
            raise TypeError("canonical current PAPER service required")
        c = service.gate.contract
        if (c.source_timezone != "UTC" or c.bar_label != "CLOSE" or not provider
                or c.provider != "NINJATRADER:" + provider
                or any(word in provider.lower() for word in ("playback", "simulat"))
                or not isinstance(expiry, str)):
            raise ValueError("explicit current provider, UTC close labels and expiry required")
        datetime.strptime(expiry, "%Y-%m-%d")
        if (type(heartbeat_seconds) not in (int, float) or not isfinite(heartbeat_seconds)
                or not 0 < heartbeat_seconds <= service.gate.maximum_age):
            raise ValueError("bounded heartbeat deadline required")
        if service._runtime is not None or service.gate.last_sequence is not None:
            raise ValueError("new isolated service required; recovery is not automatic")
        self.service, self.path = service, Path(path)
        self.provider, self.expiry = provider, expiry
        self.deadline = heartbeat_seconds
        self._lock = RLock()
        self._file = None
        self._identity = None
        self._buffer = b""
        self.session = None
        self.sequence = -1
        self.candle_sequence = 0
        self.last_event = None
        self.last_received = instant(service.gate.clock())
        self.fault = None
        self.stopped = False

    def _fail(self):
        self.fault = "NINJATRADER_TRANSPORT_RECOVERY_REQUIRED"
        if self._file is not None:
            self._file.close()
            self._file = None
        # Fail closed through the existing risk gate, without synthesizing fills.
        self.service.gate.connected = False
        try:
            self.service.gate.fail(self.fault)
        except ValueError:
            pass
        raise ValueError(self.fault) from None

    def _frame(self, raw):
        frame = json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        if set(frame) != {"schema", "session", "sequence", "event_time", "kind", "payload"}:
            raise ValueError("schema fields")
        seq = frame["sequence"]
        if frame["schema"] != SCHEMA or type(seq) is not int or seq != self.sequence + 1:
            raise ValueError("schema or sequence")
        session = frame["session"]
        if not isinstance(session, str) or str(UUID(session)) != session or (self.session is not None and session != self.session):
            raise ValueError("session changed")
        emitted, now = _utc(frame["event_time"]), instant(self.service.gate.clock())
        if not 0 <= (now-emitted).total_seconds() <= self.deadline:
            raise ValueError("stale or future transport event")
        if self.last_event is not None and emitted < self.last_event:
            raise ValueError("time regressed")
        kind, payload = frame["kind"], frame["payload"]
        if type(payload) is not dict:
            raise ValueError("payload")
        if self.session is None:
            c = self.service.gate.contract
            expected = dict(provider=self.provider, contract=c.contract, expiry=self.expiry,
                instrument="NQ", tick_size=.25, point_value=20, timeframe="1m",
                trading_hours_template=c.trading_hours_template, source_timezone="UTC",
                bar_label="CLOSE", realtime=True, read_only=True)
            if kind != "HELLO" or payload != expected or any(type(payload[k]) is not bool for k in ("realtime", "read_only")):
                raise ValueError("provider metadata not certified")
            self.session = session
            self.service.connection(True)
        elif kind == "HEARTBEAT":
            if payload != {"connected": True} or type(payload["connected"]) is not bool:
                raise ValueError("disconnected")
        elif kind in {"CLOSED", "FORMING"}:
            if set(payload) != {"bar_time", "open", "high", "low", "close", "volume"}:
                raise ValueError("candle fields")
            if any(type(payload[k]) not in (float, int) for k in ("open", "high", "low", "close")):
                raise ValueError("candle numeric types")
            label = _utc(payload["bar_time"])
            # Never let an accidentally enabled injected service create an entry.
            if self.service._runtime is not None:
                self.service.control("disable")
            self.service.ingest(CurrentMarketEventV1(
                provider=self.service.gate.contract.provider, instrument="NQ",
                contract=self.service.gate.contract.contract,
                kind="CLOSED_CANONICAL_CANDLE" if kind == "CLOSED" else "FORMING_CANDLE",
                event_time=emitted, received_at=now, bar_time=label,
                sequence=self.candle_sequence, event_id=session + ":" + str(seq),
                **{k: payload[k] for k in ("open", "high", "low", "close", "volume")}))
            self.candle_sequence += 1
        else:
            raise ValueError("unexpected state or disconnect")
        self.sequence, self.last_event, self.last_received = seq, emitted, now

    def poll(self):
        with self._lock:
            if self.stopped or self.fault:
                raise RuntimeError("STOPPED or RECOVERY_REQUIRED")
            try:
                now = instant(self.service.gate.clock())
                if not 0 <= (now-self.last_received).total_seconds() <= self.deadline:
                    raise ValueError("heartbeat timeout")
                if self._file is None:
                    self._file = self.path.open("rb")
                    stat = self.path.stat()
                    self._identity = (stat.st_dev, stat.st_ino)
                stat = self.path.stat()
                if (stat.st_dev, stat.st_ino) != self._identity or stat.st_size < self._file.tell():
                    raise ValueError("stream replaced or truncated")
                # Bounded work per poll. Backlogged frames must still be fresh.
                for _ in range(256):
                    part = self._file.readline(MAX_LINE + 1 - len(self._buffer))
                    self._buffer += part
                    if len(self._buffer) > MAX_LINE:
                        raise ValueError("oversize frame")
                    if not self._buffer.endswith(b"\n"):
                        break
                    raw, self._buffer = self._buffer, b""
                    self._frame(raw)
            except Exception:
                # Unanticipated parser/provider errors must also revoke admission.
                # Do not log untrusted frame contents or local paths.
                self._fail()
            return self.get_snapshot()

    def get_snapshot(self):
        with self._lock:
            snap = self.service.get_snapshot()
            age = (instant(self.service.gate.clock())-self.last_received).total_seconds()
            connected = self.session is not None and not self.fault and not self.stopped and 0 <= age <= self.deadline
            snap.update(paper_ready=False, dashboard_status="BLOCKED", execution_venue="LOCAL PAPER",
                external_order_authority=False, external_account_class="NOT_DISCOVERED",
                external_order_state="UNAVAILABLE", external_fill=None,
                readiness_reasons=list(dict.fromkeys(snap["readiness_reasons"] + ["READ_ONLY_PROVIDER_SMOKE"])))
            snap["provider_transport"] = dict(schema=SCHEMA, connected=connected,
                status=self.fault or ("CONNECTED" if connected else "DISCONNECTED"),
                sequence=self.sequence, expiry=self.expiry, heartbeat_age_seconds=age,
                source_timezone="UTC", native_observation_certified=False)
            snap["market_data"]["connected"] = connected
            snap["provider_state"] = "CONNECTED" if connected else "DISCONNECTED"
            snap["session_readiness"]["new_entry_admission"] = False
            if not connected:
                snap["session_readiness"].update(market_data_admission=False, strategy_admission=False,
                    readiness_status="BLOCKED", reason_code="PROVIDER_NOT_CONNECTED",
                    position_management="PRESERVE_STATE_NO_SYNTHETIC_FILL")
            return snap

    def close(self):
        with self._lock:
            self.stopped = True
            if self._file is not None:
                self._file.close()
                self._file = None
            self.service.shutdown()
