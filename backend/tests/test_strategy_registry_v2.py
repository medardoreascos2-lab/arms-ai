
import pytest

from backend.backtesting.strategy_registry_v2 import (
    StrategyRegistryV2,
)


def build_strategy():

    return {
        "strategy_id": "STR-001",
        "name": "EMA50 Smart Money",
        "version": "1.0",
        "status": "CERTIFIED",
        "grade": "A",
        "validation_score": 92.0,
        "performance_score": 85.0,
    }


def test_register_strategy():

    registry = StrategyRegistryV2()

    result = registry.register(
        build_strategy()
    )

    assert result == build_strategy()


def test_get_strategy():

    registry = StrategyRegistryV2()

    registry.register(
        build_strategy()
    )

    result = registry.get(
        "STR-001"
    )

    assert result["name"] == (
        "EMA50 Smart Money"
    )


def test_list_strategies():

    registry = StrategyRegistryV2()

    registry.register(
        build_strategy()
    )

    strategies = (
        registry.list()
    )

    assert len(strategies) == 1


def test_duplicate_strategy_rejected():

    registry = StrategyRegistryV2()

    registry.register(
        build_strategy()
    )

    with pytest.raises(
        ValueError,
    ):
        registry.register(
            build_strategy()
        )


def test_invalid_strategy_rejected():

    registry = StrategyRegistryV2()

    with pytest.raises(
        ValueError,
    ):
        registry.register(
            {
                "name": "invalid"
            }
        )
