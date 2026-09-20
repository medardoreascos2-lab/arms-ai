"""Offline future SIM contracts. No account objects or order submission API.

Metadata classification is intentionally unproven until an audited provider
adapter supplies authoritative semantics. Display names never enter this API.
"""
from dataclasses import dataclass, fields
from hashlib import sha256
import json
import sqlite3


def account_eligibility(account_class, *, authoritative=False):
    if authoritative is True and account_class == "SIMULATION":
        return "SIM_ACCOUNT_ELIGIBLE"
    if authoritative is True and account_class in {"REAL", "FUNDED", "EXTERNAL"}:
        return "REAL_ACCOUNT_INELIGIBLE"
    return "UNKNOWN_ACCOUNT_INELIGIBLE"


@dataclass(frozen=True)
class FutureSimGatesV1:
    mode: str = "DISABLED"
    account_class: str = "UNKNOWN"
    classification_proven: bool = False
    explicit_allowlist: bool = False
    market_session: str = "UNKNOWN"
    provider: str = "UNKNOWN"
    fresh_market_data: bool = False
    canonical_contract_match: bool = False
    risk_ready: bool = False
    recovery_clear: bool = False
    emergency_clear: bool = False
    native_market_certified: bool = False
    explicit_sim_authorization: bool = False

    def evaluate(self):
        failed = []
        expected = dict(mode="PAPER_RESEARCH", account_class="SIMULATION", market_session="OPEN", provider="CONNECTED")
        for field in fields(self):
            value = getattr(self, field.name)
            if (value != expected[field.name] if field.name in expected else value is not True):
                failed.append(field.name.upper())
        return dict(contract_satisfied=not failed, failed_gates=failed,
                    external_order_authority=False, sim_execution_authority="DISABLED")


def decision_identity(*, namespace, contract, decision_time, decision_id):
    # Namespace is an opaque locally generated identifier, never an account name.
    from uuid import UUID
    from backend.market_data.current_candle_authority_v1 import instant
    if str(UUID(namespace)) != namespace or not all(type(v) is str and v for v in (contract, decision_id)):
        raise ValueError("explicit identity required")
    payload = ["arms.future-sim.v1", namespace, contract, instant(decision_time).isoformat(), decision_id]
    return sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


class OfflineOrderJournalV1:
    """Durable idempotency model, not an executable order queue.

    No price, quantity, account handle, dispatcher or network dependency exists.
    Restart with pending work is quarantined. Fill/ack records describe synthetic
    test messages only; nothing here books PnL or updates portfolio state.
    """
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS intents(identity TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY, identity TEXT NOT NULL, kind TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS control(id INTEGER PRIMARY KEY CHECK(id=1), recovery INTEGER NOT NULL);
            INSERT OR IGNORE INTO control VALUES(1,0);
        """)
        with self.db:
            if self.db.execute("SELECT 1 FROM intents WHERE state IN ('PENDING','ACK')").fetchone():
                self.db.execute("UPDATE control SET recovery=1")

    @property
    def recovery_required(self):
        return bool(self.db.execute("SELECT recovery FROM control").fetchone()[0])

    def ambiguous_reconnect(self):
        with self.db:
            self.db.execute("UPDATE control SET recovery=1")

    def record(self, identity, event_id, kind):
        if self.recovery_required:
            raise RuntimeError("RECOVERY_REQUIRED")
        if not isinstance(identity, str) or len(identity) != 64 or any(c not in "0123456789abcdef" for c in identity):
            raise ValueError("digest required")
        if type(event_id) is not str or not event_id or kind not in {"DECISION", "SUBMISSION", "ACK", "FILL", "CANCEL"}:
            raise ValueError("offline event required")
        with self.db:
            prior = self.db.execute("SELECT identity,kind FROM events WHERE event_id=?", (event_id,)).fetchone()
            state = self.db.execute("SELECT state FROM intents WHERE identity=?", (identity,)).fetchone()
            if prior == (identity, kind):
                return False
            invalid = prior is not None or (state is None and kind != "DECISION")
            if not invalid and state and kind in {"DECISION", "SUBMISSION", "ACK"}:
                if kind == "DECISION" or (kind == "SUBMISSION" and state[0] in {"PENDING", "ACK", "FILLED", "CANCELLED"}) or (kind == "ACK" and state[0] in {"ACK", "FILLED", "CANCELLED"}):
                    return False
            target = {"DECISION":"DECIDED", "SUBMISSION":"PENDING", "ACK":"ACK", "FILL":"FILLED", "CANCEL":"CANCELLED"}[kind]
            allowed = {"SUBMISSION":{"DECIDED"}, "ACK":{"PENDING"}, "FILL":{"PENDING", "ACK"}, "CANCEL":{"PENDING", "ACK"}}
            if state and kind in allowed and state[0] not in allowed[kind]:
                invalid = True
            if invalid:
                self.db.execute("UPDATE control SET recovery=1")
            else:
                self.db.execute("INSERT INTO events VALUES(?,?,?)", (event_id, identity, kind))
                self.db.execute("INSERT OR REPLACE INTO intents VALUES(?,?)", (identity, target))
        if invalid:
            raise RuntimeError("RECOVERY_REQUIRED")
        return True

    def close(self):
        self.db.close()
