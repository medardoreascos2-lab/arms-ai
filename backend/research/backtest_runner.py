"""Deterministic, research-only historical backtest runner."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Callable, Mapping, Protocol

from .dataset_registry import (
    DatasetFileFormat,
    HistoricalDataset,
    HistoricalDatasetRegistry,
)


_HASH = re.compile(r"^[0-9a-f]{64}$")
_TEXT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_DECIMAL_ZERO = Decimal("0")


class ResearchBacktestError(RuntimeError):
    """The research replay could not produce a trustworthy result."""


class ResearchDataError(ResearchBacktestError):
    """Verified registry bytes are not usable deterministic bar data."""


class ResearchDeterminismError(ResearchBacktestError):
    """Equivalent replays produced different research results."""


class ResearchStrategyError(ResearchBacktestError):
    """A research strategy violated the isolated replay contract."""


class ResearchAction(str, Enum):
    HOLD = "HOLD"
    ENTER_LONG = "ENTER_LONG"
    ENTER_SHORT = "ENTER_SHORT"
    EXIT = "EXIT"


class ResearchDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


def _text(value: object, name: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    normalized = value.strip()
    if len(normalized) > 256:
        raise ValueError(f"{name} is too long")
    if identifier and _TEXT_ID.fullmatch(normalized) is None:
        raise ValueError(f"{name} is invalid")
    return normalized


def _decimal(value: object, name: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite decimal")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite decimal") from exc
    if not result.is_finite() or (positive and result <= _DECIMAL_ZERO):
        qualifier = "positive " if positive else ""
        raise ValueError(f"{name} must be a {qualifier}finite decimal")
    return result


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _utc_text(value: datetime) -> str:
    return _utc(value, "timestamp").isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _decimal_text(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in ("", "-0") else rendered


def _canonical_hash(document: object) -> str:
    encoded = json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value: {value}")


def _reject_parameter_float(value: str) -> None:
    raise ValueError(f"parameter decimals must use the $decimal tag: {value}")


def _normalize_parameter(value: object, path: str) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{path} contains a non-finite decimal")
        return {"$decimal": _decimal_text(value)}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite float")
        return {"$decimal": _decimal_text(Decimal(str(value)))}
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, nested in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError(f"{path} keys must be nonempty text")
            if key == "$decimal":
                raise ValueError(f"{path} uses the reserved $decimal key")
            if key in normalized:
                raise ValueError(f"{path} contains duplicate keys")
            normalized[key] = _normalize_parameter(nested, f"{path}.{key}")
        return normalized
    if isinstance(value, (list, tuple)):
        return [
            _normalize_parameter(nested, f"{path}[{index}]")
            for index, nested in enumerate(value)
        ]
    raise ValueError(f"{path} contains an unsupported value")


def _validate_parameter_document(value: object, path: str) -> None:
    if isinstance(value, dict):
        if "$decimal" in value:
            if set(value) != {"$decimal"} or not isinstance(value["$decimal"], str):
                raise ValueError(f"{path} has an invalid $decimal tag")
            decimal_value = _decimal(value["$decimal"], path)
            if _decimal_text(decimal_value) != value["$decimal"]:
                raise ValueError(f"{path} has a noncanonical $decimal value")
            return
        for key, nested in value.items():
            _validate_parameter_document(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_parameter_document(nested, f"{path}[{index}]")


def _restore_parameter(value: object) -> object:
    if isinstance(value, dict):
        if set(value) == {"$decimal"}:
            return Decimal(value["$decimal"])
        return {key: _restore_parameter(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_restore_parameter(nested) for nested in value]
    return value


@dataclass(frozen=True)
class ResearchParameterSet:
    canonical_json: str
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_json, str):
            raise ValueError("canonical_json must be text")
        try:
            value = json.loads(
                self.canonical_json,
                object_pairs_hook=_strict_object,
                parse_float=_reject_parameter_float,
                parse_constant=_reject_constant,
            )
        except json.JSONDecodeError as exc:
            raise ValueError("canonical_json must be strict JSON") from exc
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        if not isinstance(value, dict):
            raise ValueError("parameter set must be a JSON object")
        _validate_parameter_document(value, "parameters")
        canonical = json.dumps(
            value, ensure_ascii=False, allow_nan=False,
            sort_keys=True, separators=(",", ":"),
        )
        if canonical != self.canonical_json:
            raise ValueError("parameter set JSON must be canonical")
        object.__setattr__(self, "sha256", hashlib.sha256(canonical.encode()).hexdigest())

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "ResearchParameterSet":
        if not isinstance(values, Mapping):
            raise ValueError("parameters must be a mapping")
        normalized = _normalize_parameter(values, "parameters")
        canonical = json.dumps(
            normalized, ensure_ascii=False, allow_nan=False,
            sort_keys=True, separators=(",", ":"),
        )
        return cls(canonical)

    def as_dict(self) -> dict[str, object]:
        return _restore_parameter(json.loads(self.canonical_json))


@dataclass(frozen=True)
class ResearchStrategyIdentity:
    version: str
    sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "version", _text(self.version, "version", identifier=True))
        if not isinstance(self.sha256, str) or _HASH.fullmatch(self.sha256) is None:
            raise ValueError("strategy sha256 must be a lowercase sha256 digest")


@dataclass(frozen=True)
class ResearchCosts:
    fee_per_contract_side: Decimal
    slippage_ticks_per_side: Decimal
    tick_size: Decimal
    point_value: Decimal

    def __post_init__(self) -> None:
        for name in ("fee_per_contract_side", "slippage_ticks_per_side"):
            value = _decimal(getattr(self, name), name)
            if value < _DECIMAL_ZERO:
                raise ValueError(f"{name} cannot be negative")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "tick_size", _decimal(self.tick_size, "tick_size", positive=True))
        object.__setattr__(self, "point_value", _decimal(self.point_value, "point_value", positive=True))

    @property
    def slippage_points_per_side(self) -> Decimal:
        return self.slippage_ticks_per_side * self.tick_size

    def document(self) -> dict[str, str]:
        return {
            "fee_per_contract_side": _decimal_text(self.fee_per_contract_side),
            "point_value": _decimal_text(self.point_value),
            "slippage_ticks_per_side": _decimal_text(self.slippage_ticks_per_side),
            "tick_size": _decimal_text(self.tick_size),
        }


@dataclass(frozen=True)
class ResearchBacktestRequest:
    dataset_id: str
    strategy: ResearchStrategyIdentity
    parameters: ResearchParameterSet
    costs: ResearchCosts
    initial_balance: Decimal
    random_seed: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_id", _text(self.dataset_id, "dataset_id", identifier=True))
        if not isinstance(self.strategy, ResearchStrategyIdentity):
            raise ValueError("strategy must be ResearchStrategyIdentity")
        if not isinstance(self.parameters, ResearchParameterSet):
            raise ValueError("parameters must be ResearchParameterSet")
        if not isinstance(self.costs, ResearchCosts):
            raise ValueError("costs must be ResearchCosts")
        object.__setattr__(
            self, "initial_balance", _decimal(self.initial_balance, "initial_balance", positive=True)
        )
        if self.random_seed is not None and (
            type(self.random_seed) is not int or not -(2**63) <= self.random_seed < 2**63
        ):
            raise ValueError("random_seed must be a signed 64-bit integer or None")


@dataclass(frozen=True)
class ResearchBar:
    index: int
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class ResearchPosition:
    direction: ResearchDirection
    quantity: int
    entry_index: int
    entry_timestamp: datetime
    entry_reference_price: Decimal
    entry_price: Decimal


@dataclass(frozen=True)
class ResearchDecision:
    action: ResearchAction
    reason: str
    quantity: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.action, ResearchAction):
            raise ValueError("action must be ResearchAction")
        object.__setattr__(self, "reason", _text(self.reason, "reason"))
        if type(self.quantity) is not int or self.quantity < 1:
            raise ValueError("quantity must be a positive integer")


@dataclass(frozen=True)
class ResearchStrategyContext:
    dataset_id: str
    dataset_sha256: str
    strategy: ResearchStrategyIdentity
    parameters: ResearchParameterSet
    random_seed: int | None
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)


class ResearchStrategy(Protocol):
    def decide(
        self, bar: ResearchBar, position: ResearchPosition | None
    ) -> ResearchDecision: ...


ResearchStrategyFactory = Callable[[ResearchStrategyContext], ResearchStrategy]


@dataclass(frozen=True)
class ResearchTrade:
    direction: ResearchDirection
    quantity: int
    entry_index: int
    exit_index: int
    entry_timestamp: datetime
    exit_timestamp: datetime
    entry_reference_price: Decimal
    exit_reference_price: Decimal
    entry_price: Decimal
    exit_price: Decimal
    gross_pnl: Decimal
    fees: Decimal
    slippage_cost: Decimal
    net_pnl: Decimal
    exit_reason: str

    def document(self) -> dict[str, object]:
        return {
            "direction": self.direction.value,
            "entry_index": self.entry_index,
            "entry_price": _decimal_text(self.entry_price),
            "entry_reference_price": _decimal_text(self.entry_reference_price),
            "entry_timestamp": _utc_text(self.entry_timestamp),
            "exit_index": self.exit_index,
            "exit_price": _decimal_text(self.exit_price),
            "exit_reference_price": _decimal_text(self.exit_reference_price),
            "exit_reason": self.exit_reason,
            "exit_timestamp": _utc_text(self.exit_timestamp),
            "fees": _decimal_text(self.fees),
            "gross_pnl": _decimal_text(self.gross_pnl),
            "net_pnl": _decimal_text(self.net_pnl),
            "quantity": self.quantity,
            "slippage_cost": _decimal_text(self.slippage_cost),
        }


@dataclass(frozen=True)
class ResearchMetrics:
    initial_balance: Decimal
    ending_balance: Decimal
    net_pnl: Decimal
    gross_pnl: Decimal
    total_fees: Decimal
    total_slippage_cost: Decimal
    max_drawdown: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: Decimal | None
    profit_factor: Decimal | None
    expectancy: Decimal | None

    def document(self) -> dict[str, object]:
        return {
            "breakeven_trades": self.breakeven_trades,
            "ending_balance": _decimal_text(self.ending_balance),
            "expectancy": None if self.expectancy is None else _decimal_text(self.expectancy),
            "gross_pnl": _decimal_text(self.gross_pnl),
            "initial_balance": _decimal_text(self.initial_balance),
            "losing_trades": self.losing_trades,
            "max_drawdown": _decimal_text(self.max_drawdown),
            "net_pnl": _decimal_text(self.net_pnl),
            "profit_factor": None if self.profit_factor is None else _decimal_text(self.profit_factor),
            "total_fees": _decimal_text(self.total_fees),
            "total_slippage_cost": _decimal_text(self.total_slippage_cost),
            "total_trades": self.total_trades,
            "win_rate": None if self.win_rate is None else _decimal_text(self.win_rate),
            "winning_trades": self.winning_trades,
        }


@dataclass(frozen=True)
class ResearchDecisionSummary:
    total: int
    action_counts: tuple[tuple[str, int], ...]
    accepted_actions: int
    blocked_actions: int
    blocking_reasons: tuple[tuple[str, int], ...]
    forced_closes: int

    def document(self) -> dict[str, object]:
        return {
            "accepted_actions": self.accepted_actions,
            "action_counts": dict(self.action_counts),
            "blocked_actions": self.blocked_actions,
            "blocking_reasons": dict(self.blocking_reasons),
            "forced_closes": self.forced_closes,
            "total": self.total,
        }


@dataclass(frozen=True)
class ResearchBacktestResult:
    run_id: str
    result_hash: str
    dataset_id: str
    dataset_record_hash: str
    dataset_sha256: str
    strategy: ResearchStrategyIdentity
    parameter_set_sha256: str
    costs: ResearchCosts
    random_seed: int | None
    bar_count: int
    metrics: ResearchMetrics
    trades: tuple[ResearchTrade, ...]
    decision_summary: ResearchDecisionSummary
    deterministic_replay_verified: bool
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    live_execution_authorized: bool = field(default=False, init=False)

    def document(self, *, include_result_hash: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "bar_count": self.bar_count,
            "costs": self.costs.document(),
            "dataset_id": self.dataset_id,
            "dataset_record_hash": self.dataset_record_hash,
            "dataset_sha256": self.dataset_sha256,
            "decision_summary": self.decision_summary.document(),
            "deterministic_replay_verified": self.deterministic_replay_verified,
            "metrics": self.metrics.document(),
            "parameter_set_sha256": self.parameter_set_sha256,
            "random_seed": self.random_seed,
            "run_id": self.run_id,
            "strategy": {"sha256": self.strategy.sha256, "version": self.strategy.version},
            "trades": [trade.document() for trade in self.trades],
        }
        if include_result_hash:
            document["result_hash"] = self.result_hash
        return document


@dataclass
class _SimulationState:
    position: ResearchPosition | None = None
    trades: list[ResearchTrade] = field(default_factory=list)
    action_counts: dict[str, int] = field(default_factory=dict)
    blocking_reasons: dict[str, int] = field(default_factory=dict)
    accepted_actions: int = 0
    blocked_actions: int = 0
    forced_closes: int = 0


def _parse_timestamp(value: object, row: int) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ResearchDataError(f"bar {row} has no timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return _utc(parsed, "bar timestamp")
    except ValueError as exc:
        raise ResearchDataError(f"bar {row} has an invalid timestamp") from exc


def _bar_from_mapping(value: Mapping[str, object], index: int) -> ResearchBar:
    normalized = {str(key).strip().lower(): item for key, item in value.items()}
    timestamp = normalized.get("timestamp", normalized.get("time"))
    try:
        prices = {
            name: _decimal(normalized.get(name), f"bar {index} {name}")
            for name in ("open", "high", "low", "close", "volume")
        }
    except ValueError as exc:
        raise ResearchDataError(str(exc)) from exc
    if prices["volume"] < _DECIMAL_ZERO:
        raise ResearchDataError(f"bar {index} volume cannot be negative")
    if (
        prices["high"] < max(prices["open"], prices["close"])
        or prices["low"] > min(prices["open"], prices["close"])
        or prices["high"] < prices["low"]
    ):
        raise ResearchDataError(f"bar {index} has invalid OHLC relationships")
    return ResearchBar(
        index=index,
        timestamp=_parse_timestamp(timestamp, index),
        open=prices["open"], high=prices["high"], low=prices["low"],
        close=prices["close"], volume=prices["volume"],
    )


def _load_bars(dataset: HistoricalDataset) -> tuple[ResearchBar, ...]:
    rows: list[Mapping[str, object]] = []
    digest = hashlib.sha256()
    try:
        before_stat = dataset.path.stat()
        before = (before_stat.st_size, before_stat.st_mtime_ns, before_stat.st_ino)
        header: tuple[str, ...] | None = None
        with dataset.path.open("rb") as handle:
            for line_number, raw in enumerate(handle, start=1):
                digest.update(raw)
                text = raw.decode("utf-8-sig" if line_number == 1 else "utf-8")
                if not text.strip():
                    continue
                if dataset.file_format is DatasetFileFormat.JSONL:
                    value = json.loads(
                        text,
                        object_pairs_hook=_strict_object,
                        parse_float=Decimal,
                        parse_int=Decimal,
                        parse_constant=_reject_constant,
                    )
                    if not isinstance(value, dict):
                        raise ResearchDataError(
                            f"JSONL row {line_number} is not an object"
                        )
                    rows.append(value)
                    continue
                parsed = next(csv.reader([text], strict=True))
                if header is None:
                    header = tuple(item.strip() for item in parsed)
                    if (
                        not header
                        or any(not item for item in header)
                        or len(set(header)) != len(header)
                    ):
                        raise ResearchDataError("CSV dataset has an invalid header")
                    continue
                if len(parsed) != len(header):
                    raise ResearchDataError(
                        f"CSV row {line_number} does not match the header"
                    )
                rows.append(dict(zip(header, parsed)))
        after_stat = dataset.path.stat()
        after = (after_stat.st_size, after_stat.st_mtime_ns, after_stat.st_ino)
        if before != after:
            raise ResearchDataError("dataset changed while replay bytes were loaded")
    except (OSError, UnicodeError, csv.Error, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, ResearchDataError):
            raise
        raise ResearchDataError("verified dataset could not be parsed") from exc
    if digest.hexdigest() != dataset.sha256:
        raise ResearchDataError("replay bytes differ from the registered dataset hash")
    bars = tuple(_bar_from_mapping(row, index) for index, row in enumerate(rows))
    if len(bars) != dataset.bar_count:
        raise ResearchDataError("parsed bar count differs from registry identity")
    for previous, current in zip(bars, bars[1:]):
        if current.timestamp <= previous.timestamp:
            raise ResearchDataError("bar timestamps must be strictly increasing")
    if not bars or bars[0].timestamp < dataset.starts_at or bars[-1].timestamp > dataset.ends_at:
        raise ResearchDataError("bar timestamps are outside the registered dataset range")
    return bars


def _metrics(trades: tuple[ResearchTrade, ...], initial: Decimal) -> ResearchMetrics:
    net = sum((trade.net_pnl for trade in trades), _DECIMAL_ZERO)
    gross = sum((trade.gross_pnl for trade in trades), _DECIMAL_ZERO)
    fees = sum((trade.fees for trade in trades), _DECIMAL_ZERO)
    slippage = sum((trade.slippage_cost for trade in trades), _DECIMAL_ZERO)
    wins = [trade.net_pnl for trade in trades if trade.net_pnl > 0]
    losses = [trade.net_pnl for trade in trades if trade.net_pnl < 0]
    breakeven = len(trades) - len(wins) - len(losses)
    balance = initial
    peak = initial
    drawdown = _DECIMAL_ZERO
    for trade in trades:
        balance += trade.net_pnl
        peak = max(peak, balance)
        drawdown = max(drawdown, peak - balance)
    count = len(trades)
    gross_profit = sum(wins, _DECIMAL_ZERO)
    gross_loss = -sum(losses, _DECIMAL_ZERO)
    return ResearchMetrics(
        initial_balance=initial,
        ending_balance=initial + net,
        net_pnl=net,
        gross_pnl=gross,
        total_fees=fees,
        total_slippage_cost=slippage,
        max_drawdown=drawdown,
        total_trades=count,
        winning_trades=len(wins),
        losing_trades=len(losses),
        breakeven_trades=breakeven,
        win_rate=None if count == 0 else Decimal(len(wins)) / Decimal(count),
        profit_factor=None if gross_loss == 0 else gross_profit / gross_loss,
        expectancy=None if count == 0 else net / Decimal(count),
    )


class ResearchBacktestRunner:
    """Runs verified historical bytes with a pure research strategy factory."""

    execution_authorized = False
    production_mutation_authorized = False
    live_execution_authorized = False

    def __init__(self, registry: HistoricalDatasetRegistry):
        if not isinstance(registry, HistoricalDatasetRegistry):
            raise ValueError("registry must be HistoricalDatasetRegistry")
        self._registry = registry

    def run(
        self,
        request: ResearchBacktestRequest,
        strategy_factory: ResearchStrategyFactory,
    ) -> ResearchBacktestResult:
        if not isinstance(request, ResearchBacktestRequest):
            raise ValueError("request must be ResearchBacktestRequest")
        if not callable(strategy_factory):
            raise ValueError("strategy_factory must be callable")
        dataset = self._registry.require_verified(request.dataset_id)
        bars = _load_bars(dataset)
        run_id = _canonical_hash({
            "costs": request.costs.document(),
            "dataset_id": dataset.dataset_id,
            "dataset_record_hash": dataset.record_hash,
            "parameter_set_sha256": request.parameters.sha256,
            "random_seed": request.random_seed,
            "strategy_sha256": request.strategy.sha256,
            "strategy_version": request.strategy.version,
        })
        first = self._simulate(request, dataset, bars, strategy_factory, run_id)
        second = self._simulate(request, dataset, bars, strategy_factory, run_id)
        if first.result_hash != second.result_hash:
            raise ResearchDeterminismError("equivalent research replays diverged")
        return self._result(
            request, dataset, bars, run_id, first.trades,
            first.decision_summary, True,
        )

    def _simulate(
        self,
        request: ResearchBacktestRequest,
        dataset: HistoricalDataset,
        bars: tuple[ResearchBar, ...],
        factory: ResearchStrategyFactory,
        run_id: str,
    ) -> ResearchBacktestResult:
        context = ResearchStrategyContext(
            dataset_id=dataset.dataset_id,
            dataset_sha256=dataset.sha256,
            strategy=request.strategy,
            parameters=request.parameters,
            random_seed=request.random_seed,
        )
        try:
            strategy = factory(context)
        except Exception as exc:
            raise ResearchStrategyError("research strategy factory failed") from exc
        if not callable(getattr(strategy, "decide", None)):
            raise ResearchStrategyError("research strategy must implement decide()")
        state = _SimulationState()
        for bar in bars:
            try:
                decision = strategy.decide(bar, state.position)
            except Exception as exc:
                raise ResearchStrategyError(f"strategy failed at bar {bar.index}") from exc
            if not isinstance(decision, ResearchDecision):
                raise ResearchStrategyError("strategy returned an invalid decision")
            state.action_counts[decision.action.value] = (
                state.action_counts.get(decision.action.value, 0) + 1
            )
            self._apply_decision(state, decision, bar, bars, request.costs)
        if state.position is not None:
            state.trades.append(self._close_trade(
                state.position, bars[-1], bars[-1].close,
                request.costs, "END_OF_DATASET",
            ))
            state.position = None
            state.forced_closes += 1
        summary = ResearchDecisionSummary(
            total=len(bars),
            action_counts=tuple(sorted(state.action_counts.items())),
            accepted_actions=state.accepted_actions,
            blocked_actions=state.blocked_actions,
            blocking_reasons=tuple(sorted(state.blocking_reasons.items())),
            forced_closes=state.forced_closes,
        )
        return self._result(
            request, dataset, bars, run_id, tuple(state.trades), summary, False,
        )

    @staticmethod
    def _block(state: _SimulationState, reason: str) -> None:
        state.blocked_actions += 1
        state.blocking_reasons[reason] = state.blocking_reasons.get(reason, 0) + 1

    def _apply_decision(
        self,
        state: _SimulationState,
        decision: ResearchDecision,
        bar: ResearchBar,
        bars: tuple[ResearchBar, ...],
        costs: ResearchCosts,
    ) -> None:
        if decision.action is ResearchAction.HOLD:
            return
        if bar.index + 1 >= len(bars):
            self._block(state, "NO_NEXT_BAR")
            return
        next_bar = bars[bar.index + 1]
        if decision.action in (ResearchAction.ENTER_LONG, ResearchAction.ENTER_SHORT):
            if state.position is not None:
                self._block(state, "POSITION_ALREADY_OPEN")
                return
            direction = (
                ResearchDirection.LONG
                if decision.action is ResearchAction.ENTER_LONG
                else ResearchDirection.SHORT
            )
            adverse = costs.slippage_points_per_side
            entry = next_bar.open + adverse if direction is ResearchDirection.LONG else next_bar.open - adverse
            state.position = ResearchPosition(
                direction, decision.quantity, next_bar.index, next_bar.timestamp,
                next_bar.open, entry,
            )
            state.accepted_actions += 1
            return
        if state.position is None:
            self._block(state, "NO_OPEN_POSITION")
            return
        state.trades.append(self._close_trade(
            state.position, next_bar, next_bar.open, costs, decision.reason,
        ))
        state.position = None
        state.accepted_actions += 1

    @staticmethod
    def _close_trade(
        position: ResearchPosition,
        bar: ResearchBar,
        exit_reference_price: Decimal,
        costs: ResearchCosts,
        reason: str,
    ) -> ResearchTrade:
        sign = Decimal(1) if position.direction is ResearchDirection.LONG else Decimal(-1)
        adverse = costs.slippage_points_per_side
        exit_price = (
            exit_reference_price - adverse
            if position.direction is ResearchDirection.LONG
            else exit_reference_price + adverse
        )
        gross = (
            (exit_reference_price - position.entry_reference_price)
            * sign * Decimal(position.quantity) * costs.point_value
        )
        fees = costs.fee_per_contract_side * Decimal(position.quantity) * Decimal(2)
        slippage = (
            costs.slippage_points_per_side * Decimal(position.quantity)
            * costs.point_value * Decimal(2)
        )
        return ResearchTrade(
            direction=position.direction,
            quantity=position.quantity,
            entry_index=position.entry_index,
            exit_index=bar.index,
            entry_timestamp=position.entry_timestamp,
            exit_timestamp=bar.timestamp,
            entry_reference_price=position.entry_reference_price,
            exit_reference_price=exit_reference_price,
            entry_price=position.entry_price,
            exit_price=exit_price,
            gross_pnl=gross,
            fees=fees,
            slippage_cost=slippage,
            net_pnl=gross - fees - slippage,
            exit_reason=_text(reason, "exit_reason"),
        )

    @staticmethod
    def _result(
        request: ResearchBacktestRequest,
        dataset: HistoricalDataset,
        bars: tuple[ResearchBar, ...],
        run_id: str,
        trades: tuple[ResearchTrade, ...],
        summary: ResearchDecisionSummary,
        deterministic: bool,
    ) -> ResearchBacktestResult:
        provisional = ResearchBacktestResult(
            run_id=run_id,
            result_hash="0" * 64,
            dataset_id=dataset.dataset_id,
            dataset_record_hash=dataset.record_hash,
            dataset_sha256=dataset.sha256,
            strategy=request.strategy,
            parameter_set_sha256=request.parameters.sha256,
            costs=request.costs,
            random_seed=request.random_seed,
            bar_count=len(bars),
            metrics=_metrics(trades, request.initial_balance),
            trades=trades,
            decision_summary=summary,
            deterministic_replay_verified=deterministic,
        )
        digest = _canonical_hash(provisional.document(include_result_hash=False))
        return replace(provisional, result_hash=digest)
