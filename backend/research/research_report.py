"""Deterministic side-by-side research reporting without strategy selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import re

from .challenger_registry import ChallengerStatus, StrategyChallengerRecord


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


class ResearchReportError(RuntimeError):
    """Research report evidence is incomplete or inconsistent."""


def _text(value: object, name: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    normalized = value.strip()
    if len(normalized) > 512:
        raise ValueError(f"{name} is too long")
    if identifier and _ID.fullmatch(normalized) is None:
        raise ValueError(f"{name} is invalid")
    return normalized


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _utc_text(value: datetime) -> str:
    return _utc(value, "timestamp").isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _decimal(value: object, name: str, *, nonnegative: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite Decimal")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{name} must be a finite Decimal") from exc
    if not number.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")
    if nonnegative and number < 0:
        raise ValueError(f"{name} must be nonnegative")
    return number


def _ratio(value: object, name: str) -> Decimal:
    number = _decimal(value, name, nonnegative=True)
    if number > 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return number


def _integer(value: object, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _hash(document: dict[str, object]) -> str:
    encoded = json.dumps(
        document, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _evidence_ids(values: object) -> tuple[str, ...]:
    if not isinstance(values, tuple) or not values:
        raise ValueError("evidence_ids must be a nonempty tuple")
    normalized = tuple(sorted(_text(item, "evidence_id", identifier=True) for item in values))
    if len(set(normalized)) != len(normalized):
        raise ValueError("evidence_ids must be unique")
    return normalized


@dataclass(frozen=True)
class ResearchPerformanceMetrics:
    trade_count: int
    win_rate: Decimal
    expectancy: Decimal
    profit_factor: Decimal
    max_drawdown: Decimal
    average_r: Decimal
    mae: Decimal | None = None
    mfe: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "trade_count", _integer(
            self.trade_count, "trade_count", minimum=1
        ))
        object.__setattr__(self, "win_rate", _ratio(self.win_rate, "win_rate"))
        object.__setattr__(self, "expectancy", _decimal(self.expectancy, "expectancy"))
        object.__setattr__(self, "profit_factor", _decimal(
            self.profit_factor, "profit_factor", nonnegative=True
        ))
        object.__setattr__(self, "max_drawdown", _decimal(
            self.max_drawdown, "max_drawdown", nonnegative=True
        ))
        object.__setattr__(self, "average_r", _decimal(self.average_r, "average_r"))
        if self.mae is not None:
            object.__setattr__(self, "mae", _decimal(self.mae, "mae", nonnegative=True))
        if self.mfe is not None:
            object.__setattr__(self, "mfe", _decimal(self.mfe, "mfe", nonnegative=True))

    def document(self) -> dict[str, object]:
        return {
            "average_r": _decimal_text(self.average_r),
            "expectancy": _decimal_text(self.expectancy),
            "mae": _decimal_text(self.mae),
            "max_drawdown": _decimal_text(self.max_drawdown),
            "mfe": _decimal_text(self.mfe),
            "profit_factor": _decimal_text(self.profit_factor),
            "trade_count": self.trade_count,
            "win_rate": _decimal_text(self.win_rate),
        }


@dataclass(frozen=True)
class ResearchBreakdownRow:
    name: str
    trade_count: int
    win_rate: Decimal
    expectancy: Decimal
    net_pnl: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _text(self.name, "name", identifier=True))
        object.__setattr__(self, "trade_count", _integer(
            self.trade_count, "trade_count", minimum=1
        ))
        object.__setattr__(self, "win_rate", _ratio(self.win_rate, "win_rate"))
        object.__setattr__(self, "expectancy", _decimal(self.expectancy, "expectancy"))
        object.__setattr__(self, "net_pnl", _decimal(self.net_pnl, "net_pnl"))

    def document(self) -> dict[str, object]:
        return {
            "expectancy": _decimal_text(self.expectancy),
            "name": self.name,
            "net_pnl": _decimal_text(self.net_pnl),
            "trade_count": self.trade_count,
            "win_rate": _decimal_text(self.win_rate),
        }


def _breakdown(values: object, name: str) -> tuple[ResearchBreakdownRow, ...]:
    if not isinstance(values, tuple) or not values:
        raise ValueError(f"{name} must be a nonempty tuple")
    if any(not isinstance(item, ResearchBreakdownRow) for item in values):
        raise ValueError(f"{name} contains an invalid row")
    normalized = tuple(sorted(values, key=lambda item: item.name))
    if normalized != values or len({item.name for item in values}) != len(values):
        raise ValueError(f"{name} must be sorted with unique names")
    return normalized


def _reason_counts(values: object) -> tuple[tuple[str, int], ...]:
    if not isinstance(values, tuple):
        raise ValueError("gate_reason_breakdown must be a tuple")
    normalized: list[tuple[str, int]] = []
    for item in values:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError("gate reason row must be a name/count tuple")
        normalized.append((
            _text(item[0], "gate_reason", identifier=True),
            _integer(item[1], "gate_reason_count", minimum=1),
        ))
    result = tuple(sorted(normalized))
    if result != values or len({item[0] for item in result}) != len(result):
        raise ValueError("gate_reason_breakdown must be sorted with unique names")
    return result


@dataclass(frozen=True)
class StrategyResearchEvidence:
    strategy_id: str
    challenger_record_hash: str
    evidence_ids: tuple[str, ...]
    metrics: ResearchPerformanceMetrics
    session_breakdown: tuple[ResearchBreakdownRow, ...]
    regime_breakdown: tuple[ResearchBreakdownRow, ...]
    gate_reason_breakdown: tuple[tuple[str, int], ...]
    hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "strategy_id", _text(
            self.strategy_id, "strategy_id", identifier=True
        ))
        if not isinstance(self.challenger_record_hash, str) or _HASH.fullmatch(
            self.challenger_record_hash
        ) is None:
            raise ValueError("challenger_record_hash must be a lowercase sha256 digest")
        object.__setattr__(self, "evidence_ids", _evidence_ids(self.evidence_ids))
        if not isinstance(self.metrics, ResearchPerformanceMetrics):
            raise ValueError("metrics must be ResearchPerformanceMetrics")
        object.__setattr__(self, "session_breakdown", _breakdown(
            self.session_breakdown, "session_breakdown"
        ))
        object.__setattr__(self, "regime_breakdown", _breakdown(
            self.regime_breakdown, "regime_breakdown"
        ))
        if sum(item.trade_count for item in self.session_breakdown) != self.metrics.trade_count:
            raise ValueError("session_breakdown trade count does not reconcile")
        if sum(item.trade_count for item in self.regime_breakdown) != self.metrics.trade_count:
            raise ValueError("regime_breakdown trade count does not reconcile")
        object.__setattr__(self, "gate_reason_breakdown", _reason_counts(
            self.gate_reason_breakdown
        ))
        object.__setattr__(self, "hash", _hash(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "challenger_record_hash": self.challenger_record_hash,
            "evidence_ids": list(self.evidence_ids),
            "gate_reason_breakdown": [
                {"count": count, "reason": reason}
                for reason, count in self.gate_reason_breakdown
            ],
            "metrics": self.metrics.document(),
            "regime_breakdown": [item.document() for item in self.regime_breakdown],
            "session_breakdown": [item.document() for item in self.session_breakdown],
            "strategy_id": self.strategy_id,
        }
        if include_hash:
            document["hash"] = self.hash
        return document


@dataclass(frozen=True)
class StrategyReportSource:
    record: StrategyChallengerRecord
    evidence: StrategyResearchEvidence

    def __post_init__(self) -> None:
        if not isinstance(self.record, StrategyChallengerRecord):
            raise ValueError("record must be StrategyChallengerRecord")
        if not isinstance(self.evidence, StrategyResearchEvidence):
            raise ValueError("evidence must be StrategyResearchEvidence")
        if self.record.strategy_id != self.evidence.strategy_id:
            raise ResearchReportError("evidence strategy does not match registry record")
        if self.record.hash != self.evidence.challenger_record_hash:
            raise ResearchReportError("evidence does not bind current registry revision")
        if self.record.evidence_ids != self.evidence.evidence_ids:
            raise ResearchReportError("evidence IDs do not match registry record")


@dataclass(frozen=True)
class StrategyResearchSection:
    role: str
    strategy_id: str
    strategy_hash: str
    registry_status: ChallengerStatus
    record_hash: str
    evidence_hash: str
    evidence_ids: tuple[str, ...]
    metrics: ResearchPerformanceMetrics
    session_breakdown: tuple[ResearchBreakdownRow, ...]
    regime_breakdown: tuple[ResearchBreakdownRow, ...]
    gate_reason_breakdown: tuple[tuple[str, int], ...]

    def document(self) -> dict[str, object]:
        return {
            "evidence_hash": self.evidence_hash,
            "evidence_ids": list(self.evidence_ids),
            "gate_reason_breakdown": [
                {"count": count, "reason": reason}
                for reason, count in self.gate_reason_breakdown
            ],
            "metrics": self.metrics.document(),
            "record_hash": self.record_hash,
            "regime_breakdown": [item.document() for item in self.regime_breakdown],
            "registry_status": self.registry_status.value,
            "role": self.role,
            "session_breakdown": [item.document() for item in self.session_breakdown],
            "strategy_hash": self.strategy_hash,
            "strategy_id": self.strategy_id,
        }


@dataclass(frozen=True)
class AutomatedResearchReport:
    generated_at: datetime
    production_reference: StrategyResearchSection
    challengers: tuple[StrategyResearchSection, ...]
    report_id: str = field(init=False)
    automatic_winner_selected: bool = field(default=False, init=False)
    production_recommendation: None = field(default=None, init=False)
    human_operator_review_required: bool = field(default=True, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        generated = _utc(self.generated_at, "generated_at")
        if self.production_reference.role != "PRODUCTION_REFERENCE":
            raise ValueError("production_reference section role is invalid")
        if self.production_reference.registry_status is not ChallengerStatus.PRODUCTION_REFERENCE:
            raise ValueError("production_reference section status is invalid")
        if not isinstance(self.challengers, tuple) or not self.challengers:
            raise ValueError("report requires at least one challenger")
        if tuple(sorted(self.challengers, key=lambda item: item.strategy_id)) != self.challengers:
            raise ValueError("challengers must be sorted by strategy_id")
        if any(item.role != "CHALLENGER" for item in self.challengers):
            raise ValueError("challenger section role is invalid")
        ids = (self.production_reference.strategy_id,) + tuple(
            item.strategy_id for item in self.challengers
        )
        if len(set(ids)) != len(ids):
            raise ValueError("report strategy IDs must be unique")
        object.__setattr__(self, "generated_at", generated)
        object.__setattr__(self, "report_id", _hash(self.document(include_report_id=False)))

    def document(self, *, include_report_id: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "automatic_winner_selected": False,
            "challengers": [item.document() for item in self.challengers],
            "generated_at": _utc_text(self.generated_at),
            "human_operator_review_required": True,
            "production_recommendation": None,
            "production_reference": self.production_reference.document(),
        }
        if include_report_id:
            document["report_id"] = self.report_id
        return document


class AutomatedResearchReportBuilder:
    """Builds traceable comparisons and never ranks or promotes strategies."""

    automatic_winner_selected = False
    execution_authorized = False
    production_mutation_authorized = False

    def build(
        self,
        *,
        production_reference: StrategyReportSource,
        challengers: tuple[StrategyReportSource, ...],
        generated_at: datetime,
    ) -> AutomatedResearchReport:
        if not isinstance(production_reference, StrategyReportSource):
            raise ValueError("production_reference must be StrategyReportSource")
        if production_reference.record.status is not ChallengerStatus.PRODUCTION_REFERENCE:
            raise ResearchReportError("production report source must be PRODUCTION_REFERENCE")
        if not isinstance(challengers, tuple) or not challengers:
            raise ValueError("challengers must be a nonempty tuple")
        if any(not isinstance(item, StrategyReportSource) for item in challengers):
            raise ValueError("challengers contains an invalid source")
        if any(item.record.status is ChallengerStatus.PRODUCTION_REFERENCE for item in challengers):
            raise ResearchReportError("challenger list cannot contain production reference")
        if len({item.record.strategy_id for item in challengers}) != len(challengers):
            raise ResearchReportError("challenger strategy IDs must be unique")
        sections = tuple(sorted(
            (self._section(item, "CHALLENGER") for item in challengers),
            key=lambda item: item.strategy_id,
        ))
        return AutomatedResearchReport(
            generated_at=generated_at,
            production_reference=self._section(production_reference, "PRODUCTION_REFERENCE"),
            challengers=sections,
        )

    @staticmethod
    def _section(source: StrategyReportSource, role: str) -> StrategyResearchSection:
        return StrategyResearchSection(
            role=role,
            strategy_id=source.record.strategy_id,
            strategy_hash=source.record.strategy_hash,
            registry_status=source.record.status,
            record_hash=source.record.hash,
            evidence_hash=source.evidence.hash,
            evidence_ids=source.evidence.evidence_ids,
            metrics=source.evidence.metrics,
            session_breakdown=source.evidence.session_breakdown,
            regime_breakdown=source.evidence.regime_breakdown,
            gate_reason_breakdown=source.evidence.gate_reason_breakdown,
        )
