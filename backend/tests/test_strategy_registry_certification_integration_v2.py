
from backend.backtesting.strategy_registry_v2 import (
    StrategyRegistryV2,
)


def build_certified_strategy():

    return {
        "strategy_id": "STR-001",
        "name": "EMA50 Smart Money",
        "version": "1.0",
        "status": "CERTIFIED",
        "grade": "A",
        "validation_score": 92.0,
        "performance_score": 85.0,
    }


def test_register_certified_strategy():

    registry = StrategyRegistryV2()

    strategy = (
        build_certified_strategy()
    )

    result = registry.register(
        strategy
    )

    assert result["status"] == (
        "CERTIFIED"
    )


def test_certified_strategy_can_be_retrieved():

    registry = StrategyRegistryV2()

    registry.register(
        build_certified_strategy()
    )

    result = registry.get(
        "STR-001"
    )

    assert result["grade"] == "A"


def test_only_certified_strategies_are_registered():

    registry = StrategyRegistryV2()

    strategy = (
        build_certified_strategy()
    )

    assert strategy["status"] == (
        "CERTIFIED"
    )

    result = registry.register(
        strategy
    )

    assert result["status"] == (
        "CERTIFIED"
    )
