"""Research-only analytics for observed and hypothetical decision outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from enum import Enum
import hashlib
import json
import re


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
HYPOTHETICAL_LABEL = "HYPOTHETICAL_COUNTERFACTUAL_NOT_OBSERVED_EXECUTION"


class TraceAction(str, Enum):
    HOLD = "HOLD"
    BUY = "BUY"
    SELL = "SELL"


class TraceOutcomeKind(str, Enum):
    OBSERVED = "OBSERVED"
    HYPOTHETICAL = "HYPOTHETICAL"


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


def _decimal(value: object, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite Decimal")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{name} must be a finite Decimal") from exc
    if not number.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")
    return number


def _utc_text(value: datetime) -> str:
    return _utc(value, "timestamp").isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _named_decimal_pairs(values: object, name: str) -> tuple[tuple[str, Decimal], ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{name} must be a tuple")
    normalized = tuple(sorted(
        (_text(item[0], f"{name}_name", identifier=True), _decimal(item[1], f"{name}_value"))
        for item in values
        if isinstance(item, tuple) and len(item) == 2
    ))
    if len(normalized) != len(values):
        raise ValueError(f"{name} contains an invalid item")
    if len({item[0] for item in normalized}) != len(normalized) or normalized != values:
        raise ValueError(f"{name} must be sorted with unique names")
    return normalized


@dataclass(frozen=True)
class DecisionTraceRecord:
    trace_id: str
    timestamp: datetime
    action: TraceAction
    accepted: bool
    candidate_action: TraceAction | None
    blocking_reasons: tuple[str, ...]
    near_miss: bool
    factors: tuple[tuple[str, Decimal], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _text(self.trace_id, "trace_id", identifier=True))
        object.__setattr__(self, "timestamp", _utc(self.timestamp, "timestamp"))
        if not isinstance(self.action, TraceAction):
            raise ValueError("action must be TraceAction")
        if type(self.accepted) is not bool or type(self.near_miss) is not bool:
            raise ValueError("accepted and near_miss must be bool")
        if self.candidate_action not in {None, TraceAction.BUY, TraceAction.SELL}:
            raise ValueError("candidate_action must be BUY, SELL, or None")
        reasons = tuple(sorted(_text(item, "blocking_reason", identifier=True) for item in self.blocking_reasons))
        if len(set(reasons)) != len(reasons) or reasons != self.blocking_reasons:
            raise ValueError("blocking_reasons must be sorted and unique")
        if self.accepted and self.action is TraceAction.HOLD:
            raise ValueError("HOLD cannot be accepted")
        if self.accepted and self.blocking_reasons:
            raise ValueError("accepted decision cannot have blocking reasons")
        if not self.accepted and self.action in {TraceAction.BUY, TraceAction.SELL} and not self.blocking_reasons:
            raise ValueError("rejected entry decision requires blocking reasons")
        if self.action is TraceAction.HOLD and self.candidate_action is None and self.near_miss:
            raise ValueError("near-miss HOLD requires a candidate action")
        object.__setattr__(self, "factors", _named_decimal_pairs(self.factors, "factors"))

    def document(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "action": self.action.value,
            "blocking_reasons": list(self.blocking_reasons),
            "candidate_action": None if self.candidate_action is None else self.candidate_action.value,
            "factors": {name: format(value, "f") for name, value in self.factors},
            "near_miss": self.near_miss,
            "timestamp": _utc_text(self.timestamp),
            "trace_id": self.trace_id,
        }


@dataclass(frozen=True)
class DecisionTraceOutcome:
    trace_id: str
    kind: TraceOutcomeKind
    net_r: Decimal
    evaluated_until: datetime
    label: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _text(self.trace_id, "trace_id", identifier=True))
        if not isinstance(self.kind, TraceOutcomeKind):
            raise ValueError("kind must be TraceOutcomeKind")
        object.__setattr__(self, "net_r", _decimal(self.net_r, "net_r"))
        object.__setattr__(self, "evaluated_until", _utc(self.evaluated_until, "evaluated_until"))
        object.__setattr__(
            self,
            "label",
            "OBSERVED_EXECUTION_OUTCOME" if self.kind is TraceOutcomeKind.OBSERVED else HYPOTHETICAL_LABEL,
        )

    def document(self) -> dict[str, object]:
        return {
            "evaluated_until": _utc_text(self.evaluated_until),
            "kind": self.kind.value,
            "label": self.label,
            "net_r": format(self.net_r, "f"),
            "trace_id": self.trace_id,
        }


@dataclass(frozen=True)
class DecisionClassification:
    trace_id: str
    action: TraceAction
    outcome_kind: TraceOutcomeKind
    outcome_label: str
    net_r: Decimal
    profitable: bool
    hold_remained_poor: bool
    hold_became_profitable: bool
    gate_prevented_loss: bool
    gate_blocked_profitable_opportunity: bool
    near_miss: bool
    candidate_entry: bool
    blocking_reasons: tuple[str, ...]

    def document(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "blocking_reasons": list(self.blocking_reasons),
            "candidate_entry": self.candidate_entry,
            "gate_blocked_profitable_opportunity": self.gate_blocked_profitable_opportunity,
            "gate_prevented_loss": self.gate_prevented_loss,
            "hold_became_profitable": self.hold_became_profitable,
            "hold_remained_poor": self.hold_remained_poor,
            "near_miss": self.near_miss,
            "net_r": format(self.net_r, "f"),
            "outcome_kind": self.outcome_kind.value,
            "outcome_label": self.outcome_label,
            "profitable": self.profitable,
            "trace_id": self.trace_id,
        }


@dataclass(frozen=True)
class TraceActionSummary:
    action: TraceAction
    count: int
    profitable_count: int
    total_net_r: Decimal
    average_net_r: Decimal

    def document(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "average_net_r": format(self.average_net_r, "f"),
            "count": self.count,
            "profitable_count": self.profitable_count,
            "total_net_r": format(self.total_net_r, "f"),
        }


@dataclass(frozen=True)
class GateOutcomeSummary:
    reason: str
    blocked_count: int
    prevented_loss_count: int
    blocked_profitable_count: int

    def document(self) -> dict[str, object]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class FactorSuccessAssociation:
    factor: str
    sample_count: int
    correlation_with_profitable_outcome: Decimal | None
    interpretation: str = field(default="DESCRIPTIVE_ASSOCIATION_NOT_CAUSATION", init=False)

    def document(self) -> dict[str, object]:
        return {
            "correlation_with_profitable_outcome": (
                None if self.correlation_with_profitable_outcome is None
                else format(self.correlation_with_profitable_outcome, "f")
            ),
            "factor": self.factor,
            "interpretation": self.interpretation,
            "sample_count": self.sample_count,
        }


@dataclass(frozen=True)
class DecisionTraceAnalyticsResult:
    generated_at: datetime
    source_hash: str
    classifications: tuple[DecisionClassification, ...]
    action_summaries: tuple[TraceActionSummary, ...]
    gate_summaries: tuple[GateOutcomeSummary, ...]
    factor_associations: tuple[FactorSuccessAssociation, ...]
    near_miss_count: int
    profitable_near_miss_count: int
    candidate_entry_count: int
    result_hash: str = field(init=False)
    counterfactual_results_are_hypothetical: bool = field(default=True, init=False)
    hypothetical_label: str = field(default=HYPOTHETICAL_LABEL, init=False)
    strategy_rewrite_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", _utc(self.generated_at, "generated_at"))
        object.__setattr__(self, "result_hash", _hash(self.document(include_result_hash=False)))

    def document(self, *, include_result_hash: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "action_summaries": [item.document() for item in self.action_summaries],
            "candidate_entry_count": self.candidate_entry_count,
            "classifications": [item.document() for item in self.classifications],
            "counterfactual_results_are_hypothetical": True,
            "factor_associations": [item.document() for item in self.factor_associations],
            "gate_summaries": [item.document() for item in self.gate_summaries],
            "generated_at": _utc_text(self.generated_at),
            "hypothetical_label": HYPOTHETICAL_LABEL,
            "near_miss_count": self.near_miss_count,
            "profitable_near_miss_count": self.profitable_near_miss_count,
            "source_hash": self.source_hash,
        }
        if include_result_hash:
            document["result_hash"] = self.result_hash
        return document


class DecisionTraceResearchAnalytics:
    """Classifies trace outcomes without changing strategy or execution state."""

    strategy_rewrite_authorized = False
    execution_authorized = False

    def analyze(
        self,
        *,
        traces: tuple[DecisionTraceRecord, ...],
        outcomes: tuple[DecisionTraceOutcome, ...],
        generated_at: datetime,
    ) -> DecisionTraceAnalyticsResult:
        if not isinstance(traces, tuple) or not traces or any(
            not isinstance(item, DecisionTraceRecord) for item in traces
        ):
            raise ValueError("traces must be a nonempty tuple of DecisionTraceRecord")
        if not isinstance(outcomes, tuple) or any(
            not isinstance(item, DecisionTraceOutcome) for item in outcomes
        ):
            raise ValueError("outcomes must be a tuple of DecisionTraceOutcome")
        if len({item.trace_id for item in traces}) != len(traces):
            raise ValueError("trace IDs must be unique")
        if len({item.trace_id for item in outcomes}) != len(outcomes):
            raise ValueError("outcome trace IDs must be unique")
        trace_by_id = {item.trace_id: item for item in traces}
        outcome_by_id = {item.trace_id: item for item in outcomes}
        if set(trace_by_id) != set(outcome_by_id):
            raise ValueError("every trace must have exactly one outcome")
        ordered = tuple(sorted(traces, key=lambda item: (item.timestamp, item.trace_id)))
        classifications: list[DecisionClassification] = []
        for trace in ordered:
            outcome = outcome_by_id[trace.trace_id]
            if outcome.evaluated_until < trace.timestamp:
                raise ValueError("outcome cannot precede its trace")
            if (trace.action is TraceAction.HOLD or not trace.accepted) and outcome.kind is not TraceOutcomeKind.HYPOTHETICAL:
                raise ValueError("unexecuted decision outcomes must be HYPOTHETICAL")
            if trace.accepted and outcome.kind is not TraceOutcomeKind.OBSERVED:
                raise ValueError("accepted entry outcomes must be OBSERVED")
            profitable = outcome.net_r > 0
            blocked = bool(trace.blocking_reasons)
            classifications.append(DecisionClassification(
                trace_id=trace.trace_id,
                action=trace.action,
                outcome_kind=outcome.kind,
                outcome_label=outcome.label,
                net_r=outcome.net_r,
                profitable=profitable,
                hold_remained_poor=trace.action is TraceAction.HOLD and not profitable,
                hold_became_profitable=trace.action is TraceAction.HOLD and profitable,
                gate_prevented_loss=blocked and outcome.net_r < 0,
                gate_blocked_profitable_opportunity=blocked and profitable,
                near_miss=trace.near_miss,
                candidate_entry=trace.candidate_action is not None,
                blocking_reasons=trace.blocking_reasons,
            ))
        classification_tuple = tuple(classifications)
        source_hash = _hash({
            "outcomes": [outcome_by_id[item.trace_id].document() for item in ordered],
            "traces": [item.document() for item in ordered],
        })
        return DecisionTraceAnalyticsResult(
            generated_at=generated_at,
            source_hash=source_hash,
            classifications=classification_tuple,
            action_summaries=self._action_summaries(classification_tuple),
            gate_summaries=self._gate_summaries(classification_tuple),
            factor_associations=self._factor_associations(ordered, outcome_by_id),
            near_miss_count=sum(item.near_miss for item in classification_tuple),
            profitable_near_miss_count=sum(
                item.near_miss and item.profitable for item in classification_tuple
            ),
            candidate_entry_count=sum(item.candidate_entry for item in classification_tuple),
        )

    @staticmethod
    def _action_summaries(items: tuple[DecisionClassification, ...]):
        results = []
        for action in TraceAction:
            selected = tuple(item for item in items if item.action is action)
            total = sum((item.net_r for item in selected), Decimal(0))
            results.append(TraceActionSummary(
                action, len(selected), sum(item.profitable for item in selected),
                total, Decimal(0) if not selected else total / Decimal(len(selected)),
            ))
        return tuple(results)

    @staticmethod
    def _gate_summaries(items: tuple[DecisionClassification, ...]):
        reasons = sorted({reason for item in items for reason in item.blocking_reasons})
        return tuple(GateOutcomeSummary(
            reason=reason,
            blocked_count=sum(reason in item.blocking_reasons for item in items),
            prevented_loss_count=sum(
                reason in item.blocking_reasons and item.gate_prevented_loss for item in items
            ),
            blocked_profitable_count=sum(
                reason in item.blocking_reasons and item.gate_blocked_profitable_opportunity
                for item in items
            ),
        ) for reason in reasons)

    @staticmethod
    def _factor_associations(
        traces: tuple[DecisionTraceRecord, ...],
        outcomes: dict[str, DecisionTraceOutcome],
    ):
        names = sorted({name for trace in traces for name, _ in trace.factors})
        results = []
        for name in names:
            pairs = [
                (dict(trace.factors)[name], Decimal(1) if outcomes[trace.trace_id].net_r > 0 else Decimal(0))
                for trace in traces if name in dict(trace.factors)
            ]
            correlation = DecisionTraceResearchAnalytics._correlation(pairs)
            results.append(FactorSuccessAssociation(name, len(pairs), correlation))
        return tuple(results)

    @staticmethod
    def _correlation(pairs: list[tuple[Decimal, Decimal]]) -> Decimal | None:
        if len(pairs) < 2:
            return None
        x_mean = sum((item[0] for item in pairs), Decimal(0)) / Decimal(len(pairs))
        y_mean = sum((item[1] for item in pairs), Decimal(0)) / Decimal(len(pairs))
        numerator = sum(((x - x_mean) * (y - y_mean) for x, y in pairs), Decimal(0))
        x_square = sum(((x - x_mean) ** 2 for x, _ in pairs), Decimal(0))
        y_square = sum(((y - y_mean) ** 2 for _, y in pairs), Decimal(0))
        if x_square == 0 or y_square == 0:
            return None
        with localcontext() as context:
            context.prec = 28
            return numerator / (x_square * y_square).sqrt()
