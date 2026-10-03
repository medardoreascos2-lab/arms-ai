"""R31F tests for seeded research-only stress analysis."""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backend.research.backtest_runner import ResearchDirection, ResearchTrade
from backend.research.stress_engine import (
    ResearchStressConfig,
    ResearchStressEngine,
    ResearchStressInput,
    StressResamplingModel,
    StressTrade,
)


UTC = timezone.utc


def trade(gross, fees="10", slippage="10", quantity=1):
    gross_value = Decimal(str(gross))
    fees_value = Decimal(str(fees))
    slippage_value = Decimal(str(slippage))
    return StressTrade(
        quantity=quantity,
        gross_pnl=gross_value,
        fees=fees_value,
        slippage_cost=slippage_value,
        baseline_net_pnl=gross_value - fees_value - slippage_value,
    )


def stress_input(trades=None):
    return ResearchStressInput(
        source_run_id="1" * 64,
        source_result_hash="2" * 64,
        trades=(
            (
                trade("100"),
                trade("-50"),
                trade("50"),
                trade("-20"),
            )
            if trades is None
            else trades
        ),
    )


def config(model=StressResamplingModel.TRADE_ORDER_PERMUTATION, **changes):
    values = dict(
        iterations=25,
        seed=12345,
        model=model,
        initial_balance=Decimal("1000"),
        ruin_floor_balance=Decimal("100"),
        fee_multiplier=Decimal("1"),
        slippage_multiplier=Decimal("1"),
        additional_spread_cost_per_contract_side=Decimal("0"),
        missed_fill_probability=Decimal("0"),
    )
    values.update(changes)
    return ResearchStressConfig(**values)


def test_stress_input_reconciles_and_hashes_source_trade_evidence():
    item = stress_input()

    assert len(item.trades) == 4
    assert len(item.trades_hash) == 64
    assert len(item.hash) == 64
    assert item.document()["trade_count"] == 4
    assert item.execution_authorized is False
    assert item.production_mutation_authorized is False
    with pytest.raises(ValueError, match="does not reconcile"):
        StressTrade(1, Decimal("10"), Decimal("1"), Decimal("1"), Decimal("9"))


def test_research_trade_conversion_preserves_exact_accounting():
    record = ResearchTrade(
        direction=ResearchDirection.LONG,
        quantity=2,
        entry_index=1,
        exit_index=2,
        entry_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        exit_timestamp=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        entry_reference_price=Decimal("100"),
        exit_reference_price=Decimal("102"),
        entry_price=Decimal("100.25"),
        exit_price=Decimal("101.75"),
        gross_pnl=Decimal("80"),
        fees=Decimal("10"),
        slippage_cost=Decimal("20"),
        net_pnl=Decimal("50"),
        exit_reason="TEST",
    )

    item = ResearchStressInput.from_research_trades(
        source_run_id="1" * 64,
        source_result_hash="2" * 64,
        trades=(record,),
    )

    assert item.trades == (StressTrade(2, Decimal("80"), Decimal("10"), Decimal("20"), Decimal("50")),)


@pytest.mark.parametrize("model", tuple(StressResamplingModel))
def test_each_supported_model_is_seeded_and_deterministic(model):
    engine = ResearchStressEngine()
    settings = config(model=model)

    first = engine.run(stress_input(), settings)
    second = engine.run(stress_input(), settings)

    assert first == second
    assert first.run_id == second.run_id
    assert first.result_hash == second.result_hash
    assert len(first.simulations) == settings.iterations


def test_different_seed_changes_permutation_evidence():
    engine = ResearchStressEngine()

    first = engine.run(stress_input(), config(seed=1))
    second = engine.run(stress_input(), config(seed=2))

    assert first.run_id != second.run_id
    assert first.result_hash != second.result_hash
    assert first.simulations != second.simulations


def test_fee_slippage_and_spread_stress_reconcile_final_pnl():
    settings = config(
        iterations=1,
        fee_multiplier=Decimal("2"),
        slippage_multiplier=Decimal("3"),
        additional_spread_cost_per_contract_side=Decimal("1"),
    )

    result = ResearchStressEngine().run(stress_input(), settings)

    assert result.simulations[0].final_pnl == Decimal("-128")
    assert result.pnl_distribution.minimum == Decimal("-128")
    assert result.pnl_distribution.maximum == Decimal("-128")
    assert result.pnl_distribution.mean == Decimal("-128")


def test_missed_fill_probability_one_skips_every_trade():
    result = ResearchStressEngine().run(
        stress_input(),
        config(iterations=3, missed_fill_probability=Decimal("1")),
    )

    assert all(item.executed_trades == 0 for item in result.simulations)
    assert all(item.missed_fills == 4 for item in result.simulations)
    assert all(item.final_pnl == 0 for item in result.simulations)
    assert all(item.max_drawdown == 0 for item in result.simulations)


def test_permutation_and_bootstrap_keep_declared_path_length_without_misses():
    for model in (
        StressResamplingModel.TRADE_ORDER_PERMUTATION,
        StressResamplingModel.RETURN_BOOTSTRAP,
    ):
        result = ResearchStressEngine().run(
            stress_input(), config(model=model, iterations=5)
        )
        assert all(item.executed_trades == 4 for item in result.simulations)
        assert all(item.missed_fills == 0 for item in result.simulations)


def test_loss_streak_reshuffle_clusters_all_stressed_losses():
    result = ResearchStressEngine().run(
        stress_input(),
        config(model=StressResamplingModel.LOSS_STREAK_RESHUFFLE, iterations=10),
    )

    assert all(item.max_loss_streak == 2 for item in result.simulations)
    assert result.loss_streak_distribution.minimum == 2
    assert result.loss_streak_distribution.maximum == 2
    assert result.loss_streak_distribution.median == Decimal("2")


def test_risk_of_ruin_is_first_passage_frequency_with_explicit_assumptions():
    losing = stress_input((trade("-60", fees="0", slippage="0"),))

    result = ResearchStressEngine().run(
        losing,
        config(iterations=10, initial_balance=Decimal("100"), ruin_floor_balance=Decimal("50")),
    )

    assert result.risk_of_ruin == Decimal("1")
    assert all(item.ruined for item in result.simulations)
    assert len(result.risk_of_ruin_assumptions) == 5
    assert any("first-passage" in item for item in result.risk_of_ruin_assumptions)
    assert "not guarantees or forecasts" in result.disclaimer


def test_result_reports_all_required_distributions_and_authority_is_false():
    result = ResearchStressEngine().run(stress_input(), config())
    document = result.document()

    assert set(document["pnl_distribution"]) == {
        "minimum", "p05", "median", "mean", "p95", "maximum"
    }
    assert set(document["drawdown_distribution"]) == {
        "minimum", "p05", "median", "mean", "p95", "maximum"
    }
    assert set(document["loss_streak_distribution"]) == {
        "minimum", "p05", "median", "mean", "p95", "maximum"
    }
    assert document["config"]["seed"] == 12345
    assert document["config"]["rng_algorithm"] == "PYTHON_MT19937_RANDOM_V1"
    assert result.execution_authorized is False
    assert result.production_mutation_authorized is False
    assert result.live_execution_authorized is False


@pytest.mark.parametrize(
    "changes,match",
    (
        ({"iterations": 0}, "between 1"),
        ({"iterations": 1_000_001}, "between 1"),
        ({"seed": True}, "signed 64-bit"),
        ({"initial_balance": 0}, "must be positive"),
        ({"ruin_floor_balance": 1000}, "must be below"),
        ({"fee_multiplier": Decimal("0.9")}, "cannot be below one"),
        ({"slippage_multiplier": Decimal("0.9")}, "cannot be below one"),
        ({"missed_fill_probability": Decimal("1.1")}, "between zero and one"),
    ),
)
def test_invalid_stress_configuration_fails_closed(changes, match):
    with pytest.raises(ValueError, match=match):
        config(**changes)


def test_empty_or_invalid_source_identity_is_rejected():
    with pytest.raises(ValueError, match="nonempty tuple"):
        stress_input(())
    with pytest.raises(ValueError, match="source_run_id"):
        ResearchStressInput("not-a-hash", "2" * 64, (trade("1"),))


def test_stress_module_has_no_execution_dependencies():
    import backend.research.stress_engine as module

    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = (
        "from backend.execution", "import backend.execution", "submit_order(",
        "enterlong(", "entershort(", "broker_adapter", "requests", "httpx",
    )
    assert all(token not in source for token in forbidden)
    assert ResearchStressEngine.execution_authorized is False
    assert ResearchStressEngine.production_mutation_authorized is False
    assert ResearchStressEngine.live_execution_authorized is False
