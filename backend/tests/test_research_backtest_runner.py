"""R31B regression tests for the isolated research backtest runner."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest

from backend.research import (
    DatasetCertificationStatus,
    DatasetFileFormat,
    DatasetIntegrityError,
    DatasetWindow,
    HistoricalDatasetRegistration,
    HistoricalDatasetRegistry,
)
from backend.research.backtest_runner import (
    ResearchAction,
    ResearchBacktestRequest,
    ResearchBacktestRunner,
    ResearchCosts,
    ResearchDataError,
    ResearchDecision,
    ResearchDeterminismError,
    ResearchDirection,
    ResearchParameterSet,
    ResearchStrategyError,
    ResearchStrategyIdentity,
)


UTC = timezone.utc
START = datetime(2026, 10, 1, 14, 30, tzinfo=UTC)
STRATEGY_HASH = hashlib.sha256(b"test-strategy-v1").hexdigest()


def write_csv(path: Path) -> str:
    path.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2026-10-01T14:30:00Z,100,102,99,101,10\n"
        "2026-10-01T14:31:00Z,102,103,101,102,11\n"
        "2026-10-01T14:32:00Z,104,105,103,104,12\n"
        "2026-10-01T14:33:00Z,103,104,102,103,13\n",
        encoding="utf-8",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def registry_with_csv(tmp_path: Path):
    source = tmp_path / "bars.csv"
    digest = write_csv(source)
    registry = HistoricalDatasetRegistry((tmp_path,))
    registration = HistoricalDatasetRegistration(
        dataset_id="nq-dec26-1m-r31b",
        instrument="NQ",
        contract="NQ DEC26",
        timeframe="1m",
        session_template="CME US Index Futures ETH",
        starts_at=START,
        ends_at=START + timedelta(minutes=4),
        source="test-fixture:explicit-simulated-bars",
        window=DatasetWindow.ONE_WEEK,
        file_format=DatasetFileFormat.CSV,
        expected_bar_count=4,
        expected_sha256=digest,
        certification_status=DatasetCertificationStatus.AVAILABLE_UNCERTIFIED,
    )
    registry.register(registration, path=source, registered_at=START)
    return registry, source


def request(seed=7):
    return ResearchBacktestRequest(
        dataset_id="nq-dec26-1m-r31b",
        strategy=ResearchStrategyIdentity("test-v1", STRATEGY_HASH),
        parameters=ResearchParameterSet.from_mapping(
            {"quantity": 2, "threshold": Decimal("0.75")}
        ),
        costs=ResearchCosts(
            fee_per_contract_side=Decimal("2.50"),
            slippage_ticks_per_side=Decimal("1"),
            tick_size=Decimal("0.25"),
            point_value=Decimal("20"),
        ),
        initial_balance=Decimal("17000"),
        random_seed=seed,
    )


class EntryExitStrategy:
    def decide(self, bar, position):
        if bar.index == 0:
            return ResearchDecision(ResearchAction.ENTER_LONG, "OPEN", quantity=2)
        if bar.index == 2:
            return ResearchDecision(ResearchAction.EXIT, "SIGNAL_EXIT")
        return ResearchDecision(ResearchAction.HOLD, "NO_SIGNAL")


def test_runner_records_identity_costs_metrics_trades_and_decisions(tmp_path):
    registry, _ = registry_with_csv(tmp_path)

    result = ResearchBacktestRunner(registry).run(request(), lambda context: EntryExitStrategy())

    assert result.dataset_id == "nq-dec26-1m-r31b"
    assert result.strategy.version == "test-v1"
    assert result.parameter_set_sha256 == request().parameters.sha256
    assert result.random_seed == 7
    assert result.bar_count == 4
    assert result.deterministic_replay_verified is True
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.direction is ResearchDirection.LONG
    assert trade.entry_index == 1 and trade.exit_index == 3
    assert trade.entry_price == Decimal("102.25")
    assert trade.exit_price == Decimal("102.75")
    assert trade.entry_reference_price == Decimal("102")
    assert trade.exit_reference_price == Decimal("103")
    assert trade.gross_pnl == Decimal("40")
    assert trade.fees == Decimal("10.00")
    assert trade.slippage_cost == Decimal("20.00")
    assert trade.net_pnl == Decimal("10.00")
    assert result.metrics.net_pnl == Decimal("10.00")
    assert result.metrics.gross_pnl == Decimal("40")
    assert result.metrics.net_pnl == (
        result.metrics.gross_pnl
        - result.metrics.total_fees
        - result.metrics.total_slippage_cost
    )
    assert result.metrics.ending_balance == Decimal("17010.00")
    assert result.metrics.total_trades == 1
    assert result.decision_summary.action_counts == (
        ("ENTER_LONG", 1), ("EXIT", 1), ("HOLD", 2)
    )
    assert result.decision_summary.accepted_actions == 2
    assert result.decision_summary.blocked_actions == 0
    assert result.execution_authorized is False
    assert result.production_mutation_authorized is False
    assert result.live_execution_authorized is False


def test_equivalent_replays_have_identical_run_and_result_hashes(tmp_path):
    registry, _ = registry_with_csv(tmp_path)
    runner = ResearchBacktestRunner(registry)

    first = runner.run(request(), lambda context: EntryExitStrategy())
    second = runner.run(request(), lambda context: EntryExitStrategy())

    assert first == second
    assert first.run_id == second.run_id
    assert first.result_hash == second.result_hash
    assert first.document() == second.document()


def test_short_loss_reconciles_gross_costs_net_and_drawdown(tmp_path):
    registry, _ = registry_with_csv(tmp_path)

    class ShortStrategy:
        def decide(self, bar, position):
            if bar.index == 0:
                return ResearchDecision(ResearchAction.ENTER_SHORT, "OPEN", quantity=2)
            if bar.index == 2:
                return ResearchDecision(ResearchAction.EXIT, "SIGNAL_EXIT")
            return ResearchDecision(ResearchAction.HOLD, "HOLD")

    result = ResearchBacktestRunner(registry).run(
        request(), lambda context: ShortStrategy()
    )
    trade = result.trades[0]

    assert trade.entry_price == Decimal("101.75")
    assert trade.exit_price == Decimal("103.25")
    assert trade.gross_pnl == Decimal("-40")
    assert trade.fees == Decimal("10.00")
    assert trade.slippage_cost == Decimal("20.00")
    assert trade.net_pnl == Decimal("-70.00")
    assert result.metrics.ending_balance == Decimal("16930.00")
    assert result.metrics.max_drawdown == Decimal("70.00")
    assert result.metrics.losing_trades == 1


def test_random_seed_is_explicit_identity_and_is_given_to_factory(tmp_path):
    registry, _ = registry_with_csv(tmp_path)
    seen = []

    class Hold:
        def decide(self, bar, position):
            return ResearchDecision(ResearchAction.HOLD, "HOLD")

    first = ResearchBacktestRunner(registry).run(
        request(seed=11), lambda context: seen.append(context.random_seed) or Hold()
    )
    second = ResearchBacktestRunner(registry).run(
        request(seed=12), lambda context: seen.append(context.random_seed) or Hold()
    )

    assert seen == [11, 11, 12, 12]
    assert first.run_id != second.run_id
    assert first.result_hash != second.result_hash


def test_parameter_set_is_canonical_exact_and_immutable():
    left = ResearchParameterSet.from_mapping({"b": 2, "a": Decimal("1.20")})
    right = ResearchParameterSet.from_mapping({"a": Decimal("1.20"), "b": 2})

    assert left == right
    assert left.canonical_json == '{"a":{"$decimal":"1.2"},"b":2}'
    assert left.as_dict() == {"a": Decimal("1.2"), "b": 2}
    with pytest.raises(FrozenInstanceError):
        left.canonical_json = "{}"
    with pytest.raises(ValueError, match="canonical"):
        ResearchParameterSet('{"b":2, "a":1}')
    with pytest.raises(ValueError, match="non-finite"):
        ResearchParameterSet.from_mapping({"a": float("nan")})
    with pytest.raises(ValueError, match="must use the \\$decimal tag"):
        ResearchParameterSet('{"a":0.1}')
    with pytest.raises(ValueError, match="reserved \\$decimal key"):
        ResearchParameterSet.from_mapping({"$decimal": "1"})


@pytest.mark.parametrize(
    "costs",
    (
        dict(fee_per_contract_side="-1", slippage_ticks_per_side="0", tick_size=".25", point_value="20"),
        dict(fee_per_contract_side="1", slippage_ticks_per_side="-1", tick_size=".25", point_value="20"),
        dict(fee_per_contract_side="1", slippage_ticks_per_side="0", tick_size="0", point_value="20"),
    ),
)
def test_invalid_cost_models_fail_before_replay(costs):
    with pytest.raises(ValueError):
        ResearchCosts(**costs)


def test_changed_dataset_fails_closed_before_strategy_factory(tmp_path):
    registry, source = registry_with_csv(tmp_path)
    source.write_text(source.read_text() + "2026-10-01T14:34:00Z,1,1,1,1,1\n")
    called = []

    with pytest.raises(DatasetIntegrityError, match="not currently verified"):
        ResearchBacktestRunner(registry).run(
            request(), lambda context: called.append(True) or EntryExitStrategy()
        )

    assert called == []


def test_runner_rehashes_the_exact_bytes_it_parses(tmp_path, monkeypatch):
    registry, source = registry_with_csv(tmp_path)
    registered = registry.require_verified("nq-dec26-1m-r31b")
    source.write_text(source.read_text().replace(
        "2026-10-01T14:31:00Z,102,103,101,102,11",
        "2026-10-01T14:31:00Z,102,103,101,101,11",
    ))
    monkeypatch.setattr(registry, "require_verified", lambda dataset_id: registered)
    called = []

    with pytest.raises(ResearchDataError, match="registered dataset hash"):
        ResearchBacktestRunner(registry).run(
            request(), lambda context: called.append(True) or EntryExitStrategy()
        )

    assert called == []


def test_strategy_cannot_trade_on_last_bar_without_future_fill(tmp_path):
    registry, _ = registry_with_csv(tmp_path)

    class LastBarEntry:
        def decide(self, bar, position):
            action = ResearchAction.ENTER_LONG if bar.index == 3 else ResearchAction.HOLD
            return ResearchDecision(action, "LAST_BAR")

    result = ResearchBacktestRunner(registry).run(request(), lambda context: LastBarEntry())

    assert result.trades == ()
    assert result.decision_summary.accepted_actions == 0
    assert result.decision_summary.blocked_actions == 1
    assert result.decision_summary.blocking_reasons == (("NO_NEXT_BAR", 1),)


def test_position_conflicts_are_blocked_without_extra_trades(tmp_path):
    registry, _ = registry_with_csv(tmp_path)

    class ConflictStrategy:
        def decide(self, bar, position):
            if bar.index < 2:
                return ResearchDecision(ResearchAction.ENTER_LONG, "DUPLICATE")
            return ResearchDecision(ResearchAction.HOLD, "HOLD")

    result = ResearchBacktestRunner(registry).run(
        request(), lambda context: ConflictStrategy()
    )

    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "END_OF_DATASET"
    assert result.decision_summary.accepted_actions == 1
    assert result.decision_summary.blocking_reasons == (("POSITION_ALREADY_OPEN", 1),)
    assert result.decision_summary.forced_closes == 1


def test_exit_without_position_is_blocked(tmp_path):
    registry, _ = registry_with_csv(tmp_path)

    class ExitFlat:
        def decide(self, bar, position):
            return ResearchDecision(ResearchAction.EXIT, "EXIT_FLAT")

    result = ResearchBacktestRunner(registry).run(request(), lambda context: ExitFlat())

    assert result.trades == ()
    assert result.decision_summary.blocked_actions == 4
    assert result.decision_summary.blocking_reasons == (
        ("NO_NEXT_BAR", 1), ("NO_OPEN_POSITION", 3)
    )


def test_jsonl_dataset_replays_without_data_substitution(tmp_path):
    source = tmp_path / "bars.jsonl"
    rows = [
        {"timestamp": (START + timedelta(minutes=i)).isoformat(), "open": str(100 + i),
         "high": str(101 + i), "low": str(99 + i), "close": str(100 + i), "volume": "10"}
        for i in range(2)
    ]
    source.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    registry = HistoricalDatasetRegistry((tmp_path,))
    registry.register(
        HistoricalDatasetRegistration(
            dataset_id="jsonl-bars", instrument="NQ", contract="NQ DEC26",
            timeframe="1m", session_template="ETH", starts_at=START,
            ends_at=START + timedelta(minutes=2), source="test-jsonl",
            window=DatasetWindow.ONE_WEEK, file_format=DatasetFileFormat.JSONL,
            expected_bar_count=2,
            expected_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            certification_status=DatasetCertificationStatus.AVAILABLE_UNCERTIFIED,
        ),
        path=source,
        registered_at=START,
    )
    item = request()
    item = ResearchBacktestRequest(
        dataset_id="jsonl-bars", strategy=item.strategy, parameters=item.parameters,
        costs=item.costs, initial_balance=item.initial_balance, random_seed=item.random_seed,
    )

    result = ResearchBacktestRunner(registry).run(
        item,
        lambda context: type("Hold", (), {"decide": lambda self, bar, position: ResearchDecision(ResearchAction.HOLD, "HOLD")})(),
    )

    assert result.bar_count == 2
    assert result.dataset_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()


def test_non_monotonic_or_out_of_range_bars_are_rejected(tmp_path):
    registry, source = registry_with_csv(tmp_path)
    content = source.read_text().replace(
        "2026-10-01T14:31:00Z", "2026-10-01T14:30:00Z"
    )
    source.write_text(content)
    # Register the now internally invalid bytes accurately: registry identity succeeds,
    # while the runner rejects their temporal semantics without fabricating a replay.
    registry = HistoricalDatasetRegistry((tmp_path,))
    registry.register(
        HistoricalDatasetRegistration(
            dataset_id="nq-dec26-1m-r31b", instrument="NQ", contract="NQ DEC26",
            timeframe="1m", session_template="ETH", starts_at=START,
            ends_at=START + timedelta(minutes=4), source="invalid-order-fixture",
            window=DatasetWindow.ONE_WEEK, file_format=DatasetFileFormat.CSV,
            expected_bar_count=4,
            expected_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            certification_status=DatasetCertificationStatus.AVAILABLE_UNCERTIFIED,
        ), path=source, registered_at=START,
    )

    with pytest.raises(ResearchDataError, match="strictly increasing"):
        ResearchBacktestRunner(registry).run(request(), lambda context: EntryExitStrategy())


def test_strategy_failure_or_invalid_output_never_returns_partial_result(tmp_path):
    registry, _ = registry_with_csv(tmp_path)

    class Explodes:
        def decide(self, bar, position):
            raise RuntimeError("boom")

    class Invalid:
        def decide(self, bar, position):
            return {"action": "HOLD"}

    runner = ResearchBacktestRunner(registry)
    with pytest.raises(ResearchStrategyError, match="failed at bar"):
        runner.run(request(), lambda context: Explodes())
    with pytest.raises(ResearchStrategyError, match="invalid decision"):
        runner.run(request(), lambda context: Invalid())


def test_nondeterministic_strategy_is_rejected(tmp_path):
    registry, _ = registry_with_csv(tmp_path)
    factory_calls = 0

    class Variable:
        def __init__(self, enter):
            self.enter = enter

        def decide(self, bar, position):
            if self.enter and bar.index == 0:
                return ResearchDecision(ResearchAction.ENTER_LONG, "VARIABLE")
            return ResearchDecision(ResearchAction.HOLD, "HOLD")

    def factory(context):
        nonlocal factory_calls
        factory_calls += 1
        return Variable(factory_calls == 1)

    with pytest.raises(ResearchDeterminismError, match="diverged"):
        ResearchBacktestRunner(registry).run(request(), factory)


def test_runner_source_has_no_production_execution_dependencies():
    import backend.research.backtest_runner as module

    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = (
        "from backend.execution", "import backend.execution", "enterlong(",
        "entershort(", "submit_order(", "broker_adapter", "requests", "httpx",
    )
    assert all(token not in source for token in forbidden)
    assert ResearchBacktestRunner.execution_authorized is False
    assert ResearchBacktestRunner.production_mutation_authorized is False
    assert ResearchBacktestRunner.live_execution_authorized is False
