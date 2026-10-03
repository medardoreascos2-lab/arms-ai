"""Seeded research-only Monte Carlo and cost stress analysis."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
import random
import re

from .backtest_runner import ResearchTrade, _decimal_text


_HASH = re.compile(r"^[0-9a-f]{64}$")
_DISCLAIMER = (
    "Research stress results depend on explicit model assumptions and are not "
    "guarantees or forecasts of future performance."
)
_RNG_ALGORITHM = "PYTHON_MT19937_RANDOM_V1"
_MAX_ITERATIONS = 1_000_000
_RISK_ASSUMPTIONS = (
    "Empirical trade outcomes are treated as exchangeable only under the selected resampling model.",
    "Fee, slippage, and spread stresses are fixed scenario inputs rather than forecasts.",
    "Missed fills are independent Bernoulli events under the configured probability.",
    "Risk of ruin is the simulated first-passage frequency at the configured equity floor.",
    "Market regime changes and serial dependence are absent unless represented by the selected model.",
)


class ResearchStressError(RuntimeError):
    """The stress run cannot produce trustworthy research evidence."""


class StressResamplingModel(str, Enum):
    TRADE_ORDER_PERMUTATION = "TRADE_ORDER_PERMUTATION"
    LOSS_STREAK_RESHUFFLE = "LOSS_STREAK_RESHUFFLE"
    RETURN_BOOTSTRAP = "RETURN_BOOTSTRAP"


def _decimal(value: object, name: str, *, nonnegative: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite decimal")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite decimal") from exc
    if not result.is_finite() or (nonnegative and result < 0):
        raise ValueError(f"{name} must be a finite nonnegative decimal")
    return result


def _hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_hash(value: object, name: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase sha256 digest")
    return value


@dataclass(frozen=True)
class StressTrade:
    quantity: int
    gross_pnl: Decimal
    fees: Decimal
    slippage_cost: Decimal
    baseline_net_pnl: Decimal

    def __post_init__(self) -> None:
        if type(self.quantity) is not int or self.quantity < 1:
            raise ValueError("quantity must be a positive integer")
        object.__setattr__(self, "gross_pnl", _decimal(self.gross_pnl, "gross_pnl"))
        object.__setattr__(self, "fees", _decimal(self.fees, "fees", nonnegative=True))
        object.__setattr__(
            self,
            "slippage_cost",
            _decimal(self.slippage_cost, "slippage_cost", nonnegative=True),
        )
        object.__setattr__(
            self, "baseline_net_pnl", _decimal(self.baseline_net_pnl, "baseline_net_pnl")
        )
        if self.baseline_net_pnl != self.gross_pnl - self.fees - self.slippage_cost:
            raise ValueError("baseline trade PnL does not reconcile")

    @classmethod
    def from_research_trade(cls, trade: ResearchTrade) -> "StressTrade":
        if not isinstance(trade, ResearchTrade):
            raise ValueError("trade must be ResearchTrade")
        return cls(
            quantity=trade.quantity,
            gross_pnl=trade.gross_pnl,
            fees=trade.fees,
            slippage_cost=trade.slippage_cost,
            baseline_net_pnl=trade.net_pnl,
        )

    def document(self) -> dict[str, object]:
        return {
            "baseline_net_pnl": _decimal_text(self.baseline_net_pnl),
            "fees": _decimal_text(self.fees),
            "gross_pnl": _decimal_text(self.gross_pnl),
            "quantity": self.quantity,
            "slippage_cost": _decimal_text(self.slippage_cost),
        }


@dataclass(frozen=True)
class ResearchStressInput:
    source_run_id: str
    source_result_hash: str
    trades: tuple[StressTrade, ...]
    trades_hash: str = field(init=False)
    hash: str = field(init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        _require_hash(self.source_run_id, "source_run_id")
        _require_hash(self.source_result_hash, "source_result_hash")
        if not isinstance(self.trades, tuple) or not self.trades:
            raise ValueError("trades must be a nonempty tuple")
        if any(not isinstance(trade, StressTrade) for trade in self.trades):
            raise ValueError("trades must contain StressTrade values")
        trades_hash = _hash([trade.document() for trade in self.trades])
        object.__setattr__(self, "trades_hash", trades_hash)
        object.__setattr__(self, "hash", _hash({
            "source_result_hash": self.source_result_hash,
            "source_run_id": self.source_run_id,
            "trades_hash": trades_hash,
        }))

    @classmethod
    def from_research_trades(
        cls,
        *,
        source_run_id: str,
        source_result_hash: str,
        trades: tuple[ResearchTrade, ...],
    ) -> "ResearchStressInput":
        if not isinstance(trades, tuple):
            raise ValueError("trades must be a tuple")
        return cls(
            source_run_id=source_run_id,
            source_result_hash=source_result_hash,
            trades=tuple(StressTrade.from_research_trade(trade) for trade in trades),
        )

    def document(self) -> dict[str, object]:
        return {
            "hash": self.hash,
            "source_result_hash": self.source_result_hash,
            "source_run_id": self.source_run_id,
            "trade_count": len(self.trades),
            "trades_hash": self.trades_hash,
        }


@dataclass(frozen=True)
class ResearchStressConfig:
    iterations: int
    seed: int
    model: StressResamplingModel
    initial_balance: Decimal
    ruin_floor_balance: Decimal
    fee_multiplier: Decimal = Decimal("1")
    slippage_multiplier: Decimal = Decimal("1")
    additional_spread_cost_per_contract_side: Decimal = Decimal("0")
    missed_fill_probability: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if (
            type(self.iterations) is not int
            or self.iterations < 1
            or self.iterations > _MAX_ITERATIONS
        ):
            raise ValueError("iterations must be between 1 and 1000000")
        if type(self.seed) is not int or not -(2**63) <= self.seed < 2**63:
            raise ValueError("seed must be a signed 64-bit integer")
        if not isinstance(self.model, StressResamplingModel):
            raise ValueError("model must be StressResamplingModel")
        initial = _decimal(self.initial_balance, "initial_balance")
        floor = _decimal(self.ruin_floor_balance, "ruin_floor_balance", nonnegative=True)
        if initial <= 0:
            raise ValueError("initial_balance must be positive")
        if floor >= initial:
            raise ValueError("ruin_floor_balance must be below initial_balance")
        object.__setattr__(self, "initial_balance", initial)
        object.__setattr__(self, "ruin_floor_balance", floor)
        for name in (
            "fee_multiplier",
            "slippage_multiplier",
            "additional_spread_cost_per_contract_side",
            "missed_fill_probability",
        ):
            object.__setattr__(
                self, name, _decimal(getattr(self, name), name, nonnegative=True)
            )
        if self.fee_multiplier < 1 or self.slippage_multiplier < 1:
            raise ValueError("fee and slippage stress multipliers cannot be below one")
        if self.missed_fill_probability > 1:
            raise ValueError("missed_fill_probability must be between zero and one")

    def document(self) -> dict[str, object]:
        return {
            "additional_spread_cost_per_contract_side": _decimal_text(
                self.additional_spread_cost_per_contract_side
            ),
            "fee_multiplier": _decimal_text(self.fee_multiplier),
            "initial_balance": _decimal_text(self.initial_balance),
            "iterations": self.iterations,
            "missed_fill_probability": _decimal_text(self.missed_fill_probability),
            "model": self.model.value,
            "rng_algorithm": _RNG_ALGORITHM,
            "ruin_floor_balance": _decimal_text(self.ruin_floor_balance),
            "seed": self.seed,
            "slippage_multiplier": _decimal_text(self.slippage_multiplier),
        }


@dataclass(frozen=True)
class StressSimulation:
    index: int
    final_pnl: Decimal
    max_drawdown: Decimal
    max_loss_streak: int
    executed_trades: int
    missed_fills: int
    ruined: bool

    def document(self) -> dict[str, object]:
        return {
            "executed_trades": self.executed_trades,
            "final_pnl": _decimal_text(self.final_pnl),
            "index": self.index,
            "max_drawdown": _decimal_text(self.max_drawdown),
            "max_loss_streak": self.max_loss_streak,
            "missed_fills": self.missed_fills,
            "ruined": self.ruined,
        }


@dataclass(frozen=True)
class DecimalDistribution:
    minimum: Decimal
    p05: Decimal
    median: Decimal
    mean: Decimal
    p95: Decimal
    maximum: Decimal

    def document(self) -> dict[str, str]:
        return {
            "maximum": _decimal_text(self.maximum),
            "mean": _decimal_text(self.mean),
            "median": _decimal_text(self.median),
            "minimum": _decimal_text(self.minimum),
            "p05": _decimal_text(self.p05),
            "p95": _decimal_text(self.p95),
        }


@dataclass(frozen=True)
class IntegerDistribution:
    minimum: int
    p05: int
    median: Decimal
    mean: Decimal
    p95: int
    maximum: int

    def document(self) -> dict[str, object]:
        return {
            "maximum": self.maximum,
            "mean": _decimal_text(self.mean),
            "median": _decimal_text(self.median),
            "minimum": self.minimum,
            "p05": self.p05,
            "p95": self.p95,
        }


def _nearest_rank(values: tuple[object, ...], percentile: int):
    index = max(0, ((percentile * len(values) + 99) // 100) - 1)
    return values[index]


def _median(values: tuple[Decimal, ...]) -> Decimal:
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / Decimal(2)


def _decimal_distribution(values: tuple[Decimal, ...]) -> DecimalDistribution:
    ordered = tuple(sorted(values))
    return DecimalDistribution(
        minimum=ordered[0],
        p05=_nearest_rank(ordered, 5),
        median=_median(ordered),
        mean=sum(ordered, Decimal(0)) / Decimal(len(ordered)),
        p95=_nearest_rank(ordered, 95),
        maximum=ordered[-1],
    )


def _integer_distribution(values: tuple[int, ...]) -> IntegerDistribution:
    ordered = tuple(sorted(values))
    return IntegerDistribution(
        minimum=ordered[0],
        p05=_nearest_rank(ordered, 5),
        median=_median(tuple(Decimal(value) for value in ordered)),
        mean=Decimal(sum(ordered)) / Decimal(len(ordered)),
        p95=_nearest_rank(ordered, 95),
        maximum=ordered[-1],
    )


@dataclass(frozen=True)
class ResearchStressResult:
    run_id: str
    result_hash: str
    input_hash: str
    config: ResearchStressConfig
    simulations: tuple[StressSimulation, ...]
    pnl_distribution: DecimalDistribution
    drawdown_distribution: DecimalDistribution
    loss_streak_distribution: IntegerDistribution
    risk_of_ruin: Decimal
    risk_of_ruin_assumptions: tuple[str, ...]
    disclaimer: str
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    live_execution_authorized: bool = field(default=False, init=False)

    def document(self, *, include_result_hash: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "config": self.config.document(),
            "disclaimer": self.disclaimer,
            "drawdown_distribution": self.drawdown_distribution.document(),
            "input_hash": self.input_hash,
            "loss_streak_distribution": self.loss_streak_distribution.document(),
            "pnl_distribution": self.pnl_distribution.document(),
            "risk_of_ruin": _decimal_text(self.risk_of_ruin),
            "risk_of_ruin_assumptions": list(self.risk_of_ruin_assumptions),
            "run_id": self.run_id,
            "simulations": [simulation.document() for simulation in self.simulations],
        }
        if include_result_hash:
            document["result_hash"] = self.result_hash
        return document


class ResearchStressEngine:
    """Applies explicit seeded resampling and execution-cost stresses."""

    execution_authorized = False
    production_mutation_authorized = False
    live_execution_authorized = False

    def run(
        self,
        stress_input: ResearchStressInput,
        config: ResearchStressConfig,
    ) -> ResearchStressResult:
        if not isinstance(stress_input, ResearchStressInput):
            raise ValueError("stress_input must be ResearchStressInput")
        if not isinstance(config, ResearchStressConfig):
            raise ValueError("config must be ResearchStressConfig")
        run_id = _hash({
            "config": config.document(),
            "input_hash": stress_input.hash,
        })
        rng = random.Random(config.seed)
        stressed = tuple(self._stressed_pnl(trade, config) for trade in stress_input.trades)
        simulations = tuple(
            self._simulate(index, stressed, rng, config)
            for index in range(config.iterations)
        )
        pnl = tuple(item.final_pnl for item in simulations)
        drawdowns = tuple(item.max_drawdown for item in simulations)
        streaks = tuple(item.max_loss_streak for item in simulations)
        risk = Decimal(sum(1 for item in simulations if item.ruined)) / Decimal(len(simulations))
        provisional = ResearchStressResult(
            run_id=run_id,
            result_hash="0" * 64,
            input_hash=stress_input.hash,
            config=config,
            simulations=simulations,
            pnl_distribution=_decimal_distribution(pnl),
            drawdown_distribution=_decimal_distribution(drawdowns),
            loss_streak_distribution=_integer_distribution(streaks),
            risk_of_ruin=risk,
            risk_of_ruin_assumptions=_RISK_ASSUMPTIONS,
            disclaimer=_DISCLAIMER,
        )
        result_hash = _hash(provisional.document(include_result_hash=False))
        return replace(provisional, result_hash=result_hash)

    @staticmethod
    def _stressed_pnl(trade: StressTrade, config: ResearchStressConfig) -> Decimal:
        spread_cost = (
            config.additional_spread_cost_per_contract_side
            * Decimal(2)
            * Decimal(trade.quantity)
        )
        return (
            trade.gross_pnl
            - trade.fees * config.fee_multiplier
            - trade.slippage_cost * config.slippage_multiplier
            - spread_cost
        )

    @staticmethod
    def _ordered(
        values: tuple[Decimal, ...],
        rng: random.Random,
        model: StressResamplingModel,
    ) -> list[Decimal]:
        if model is StressResamplingModel.RETURN_BOOTSTRAP:
            return [rng.choice(values) for _ in values]
        if model is StressResamplingModel.TRADE_ORDER_PERMUTATION:
            result = list(values)
            rng.shuffle(result)
            return result
        losses = [value for value in values if value < 0]
        others = [value for value in values if value >= 0]
        rng.shuffle(losses)
        rng.shuffle(others)
        insertion = rng.randrange(len(others) + 1)
        return others[:insertion] + losses + others[insertion:]

    def _simulate(
        self,
        index: int,
        values: tuple[Decimal, ...],
        rng: random.Random,
        config: ResearchStressConfig,
    ) -> StressSimulation:
        ordered = self._ordered(values, rng, config.model)
        kept = []
        missed = 0
        threshold = config.missed_fill_probability
        for value in ordered:
            draw = Decimal(str(rng.random()))
            if draw < threshold:
                missed += 1
            else:
                kept.append(value)
        balance = config.initial_balance
        peak = balance
        drawdown = Decimal(0)
        loss_streak = 0
        max_loss_streak = 0
        ruined = balance <= config.ruin_floor_balance
        for value in kept:
            balance += value
            peak = max(peak, balance)
            drawdown = max(drawdown, peak - balance)
            if value < 0:
                loss_streak += 1
                max_loss_streak = max(max_loss_streak, loss_streak)
            else:
                loss_streak = 0
            if balance <= config.ruin_floor_balance:
                ruined = True
        return StressSimulation(
            index=index,
            final_pnl=balance - config.initial_balance,
            max_drawdown=drawdown,
            max_loss_streak=max_loss_streak,
            executed_trades=len(kept),
            missed_fills=missed,
            ruined=ruined,
        )
