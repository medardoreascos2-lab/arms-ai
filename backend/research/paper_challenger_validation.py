"""Isolated PAPER challenger evidence with no broker or LIVE authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import re


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


def _id(value: object, name: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{name} is invalid")
    return value


def _sha(value: object, name: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase SHA-256")
    return value


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _dec(value: object, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite Decimal")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{name} must be a finite Decimal") from exc
    if not number.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")
    return number


def _time(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class PaperStrategyIdentity:
    strategy_id: str
    strategy_hash: str
    registry_record_hash: str
    registry_revision: int
    role: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "strategy_id", _id(self.strategy_id, "strategy_id"))
        object.__setattr__(self, "strategy_hash", _sha(self.strategy_hash, "strategy_hash"))
        object.__setattr__(self, "registry_record_hash", _sha(self.registry_record_hash, "registry_record_hash"))
        if type(self.registry_revision) is not int or self.registry_revision < 0:
            raise ValueError("registry_revision must be nonnegative")
        if self.role not in {"PAPER_CHALLENGER", "PRODUCTION_REFERENCE"}:
            raise ValueError("role is invalid")

    def document(self) -> dict[str, object]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class PaperTradeEvidence:
    trade_id: str
    session_id: str
    opened_at: datetime
    closed_at: datetime
    net_r: Decimal
    simulated: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "trade_id", _id(self.trade_id, "trade_id"))
        object.__setattr__(self, "session_id", _id(self.session_id, "session_id"))
        object.__setattr__(self, "opened_at", _utc(self.opened_at, "opened_at"))
        object.__setattr__(self, "closed_at", _utc(self.closed_at, "closed_at"))
        object.__setattr__(self, "net_r", _dec(self.net_r, "net_r"))
        if self.closed_at < self.opened_at:
            raise ValueError("closed_at cannot precede opened_at")
        if self.simulated is not True:
            raise ValueError("paper trade evidence must be simulated")

    def document(self) -> dict[str, object]:
        return {"closed_at": _time(self.closed_at), "net_r": format(self.net_r, "f"),
                "opened_at": _time(self.opened_at), "session_id": self.session_id,
                "simulated": self.simulated, "trade_id": self.trade_id}


@dataclass(frozen=True)
class PaperFaultEvidence:
    fault_id: str
    session_id: str
    occurred_at: datetime
    code: str
    detail: str

    def __post_init__(self) -> None:
        for name in ("fault_id", "session_id", "code"):
            object.__setattr__(self, name, _id(getattr(self, name), name))
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at, "occurred_at"))
        if not isinstance(self.detail, str) or not self.detail.strip() or len(self.detail) > 512:
            raise ValueError("detail must be nonempty bounded text")

    def document(self) -> dict[str, object]:
        return {"code": self.code, "detail": self.detail, "fault_id": self.fault_id,
                "occurred_at": _time(self.occurred_at), "session_id": self.session_id}


@dataclass(frozen=True)
class PaperSessionEvidence:
    session_id: str
    candidate_id: str
    started_at: datetime
    ended_at: datetime
    trades: tuple[PaperTradeEvidence, ...]
    faults: tuple[PaperFaultEvidence, ...]
    session_hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", _id(self.session_id, "session_id"))
        object.__setattr__(self, "candidate_id", _id(self.candidate_id, "candidate_id"))
        object.__setattr__(self, "started_at", _utc(self.started_at, "started_at"))
        object.__setattr__(self, "ended_at", _utc(self.ended_at, "ended_at"))
        if self.ended_at < self.started_at:
            raise ValueError("ended_at cannot precede started_at")
        if not isinstance(self.trades, tuple) or not isinstance(self.faults, tuple):
            raise ValueError("trades and faults must be tuples")
        if any(item.session_id != self.session_id for item in self.trades + self.faults):
            raise ValueError("session evidence identity mismatch")
        ids = [item.trade_id for item in self.trades] + [item.fault_id for item in self.faults]
        if len(ids) != len(set(ids)):
            raise ValueError("session evidence ids must be unique")
        if tuple(sorted(self.trades, key=lambda item: item.trade_id)) != self.trades or tuple(sorted(self.faults, key=lambda item: item.fault_id)) != self.faults:
            raise ValueError("session evidence must be sorted")
        if any(item.opened_at < self.started_at or item.closed_at > self.ended_at for item in self.trades):
            raise ValueError("trade falls outside session")
        if any(item.occurred_at < self.started_at or item.occurred_at > self.ended_at for item in self.faults):
            raise ValueError("fault falls outside session")
        object.__setattr__(self, "session_hash", _hash(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        value = {"candidate_id": self.candidate_id, "ended_at": _time(self.ended_at),
                 "faults": [item.document() for item in self.faults], "session_id": self.session_id,
                 "started_at": _time(self.started_at), "trades": [item.document() for item in self.trades]}
        if include_hash:
            value["session_hash"] = self.session_hash
        return value


@dataclass(frozen=True)
class PaperValidationMetrics:
    trade_count: int
    profitable_count: int
    total_net_r: Decimal
    average_net_r: Decimal
    max_drawdown_r: Decimal

    def __post_init__(self) -> None:
        if type(self.trade_count) is not int or self.trade_count < 0:
            raise ValueError("trade_count is invalid")
        if type(self.profitable_count) is not int or not 0 <= self.profitable_count <= self.trade_count:
            raise ValueError("profitable_count is invalid")
        for name in ("total_net_r", "average_net_r", "max_drawdown_r"):
            object.__setattr__(self, name, _dec(getattr(self, name), name))
        if self.max_drawdown_r < 0:
            raise ValueError("max_drawdown_r must be nonnegative")
        expected = Decimal("0") if self.trade_count == 0 else self.total_net_r / Decimal(self.trade_count)
        if self.average_net_r != expected:
            raise ValueError("average_net_r does not reconcile")

    def document(self) -> dict[str, object]:
        return {"average_net_r": format(self.average_net_r, "f"), "max_drawdown_r": format(self.max_drawdown_r, "f"),
                "profitable_count": self.profitable_count, "total_net_r": format(self.total_net_r, "f"), "trade_count": self.trade_count}


@dataclass(frozen=True)
class PaperReferenceComparison:
    candidate: PaperValidationMetrics
    production_reference: PaperValidationMetrics
    average_net_r_delta: Decimal = field(init=False)
    max_drawdown_r_delta: Decimal = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "average_net_r_delta", self.candidate.average_net_r - self.production_reference.average_net_r)
        object.__setattr__(self, "max_drawdown_r_delta", self.candidate.max_drawdown_r - self.production_reference.max_drawdown_r)

    def document(self) -> dict[str, object]:
        return {"average_net_r_delta": format(self.average_net_r_delta, "f"), "candidate": self.candidate.document(),
                "max_drawdown_r_delta": format(self.max_drawdown_r_delta, "f"), "production_reference": self.production_reference.document()}


@dataclass(frozen=True)
class PaperChallengerValidationReport:
    generated_at: datetime
    candidate: PaperStrategyIdentity
    production_reference: PaperStrategyIdentity
    sessions: tuple[PaperSessionEvidence, ...]
    comparison: PaperReferenceComparison
    source_hash: str
    report_hash: str = field(init=False)
    execution_kind: str = field(default="SIMULATED_PAPER", init=False)
    broker_execution_authorized: bool = field(default=False, init=False)
    live_execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", _utc(self.generated_at, "generated_at"))
        if self.candidate.role != "PAPER_CHALLENGER" or self.production_reference.role != "PRODUCTION_REFERENCE":
            raise ValueError("strategy roles do not match report boundaries")
        if not isinstance(self.sessions, tuple) or not self.sessions:
            raise ValueError("sessions must be a nonempty tuple")
        if tuple(sorted(self.sessions, key=lambda item: item.session_id)) != self.sessions:
            raise ValueError("sessions must be sorted")
        if any(item.candidate_id != self.candidate.strategy_id for item in self.sessions):
            raise ValueError("session candidate identity mismatch")
        object.__setattr__(self, "source_hash", _sha(self.source_hash, "source_hash"))
        object.__setattr__(self, "report_hash", _hash(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        value = {"broker_execution_authorized": self.broker_execution_authorized, "candidate": self.candidate.document(),
                 "comparison": self.comparison.document(), "execution_kind": self.execution_kind, "generated_at": _time(self.generated_at),
                 "live_execution_authorized": self.live_execution_authorized, "production_mutation_authorized": self.production_mutation_authorized,
                 "production_reference": self.production_reference.document(), "sessions": [item.document() for item in self.sessions], "source_hash": self.source_hash}
        if include_hash:
            value["report_hash"] = self.report_hash
        return value


class PaperChallengerValidationModel:
    def build(self, *, candidate: PaperStrategyIdentity, production_reference: PaperStrategyIdentity,
              sessions: tuple[PaperSessionEvidence, ...], reference_metrics: PaperValidationMetrics,
              generated_at: datetime) -> PaperChallengerValidationReport:
        ordered = tuple(sorted(sessions, key=lambda item: item.session_id))
        trades = tuple(trade for session in ordered for trade in session.trades)
        candidate_metrics = self._metrics(trades)
        source = {"candidate": candidate.document(), "production_reference": production_reference.document(),
                  "reference_metrics": reference_metrics.document(), "sessions": [item.document() for item in ordered]}
        return PaperChallengerValidationReport(generated_at, candidate, production_reference, ordered,
                                               PaperReferenceComparison(candidate_metrics, reference_metrics), _hash(source))

    @staticmethod
    def _metrics(trades: tuple[PaperTradeEvidence, ...]) -> PaperValidationMetrics:
        total = sum((item.net_r for item in trades), Decimal("0"))
        equity = peak = drawdown = Decimal("0")
        for trade in sorted(trades, key=lambda item: (item.closed_at, item.trade_id)):
            equity += trade.net_r
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        return PaperValidationMetrics(len(trades), sum(item.net_r > 0 for item in trades), total,
                                      Decimal("0") if not trades else total / Decimal(len(trades)), drawdown)
