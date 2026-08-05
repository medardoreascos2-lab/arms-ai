
from backend.backtesting.strategy_registry_v2 import (
    StrategyRegistryV2,
)

from backend.backtesting.strategy_certification_registry_service_v2 import (
    StrategyCertificationRegistryServiceV2,
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


def test_certified_strategy_is_saved_in_registry():

    registry = StrategyRegistryV2()

    service = (
        StrategyCertificationRegistryServiceV2(
            registry=registry,
        )
    )


    result = (
        service.register_certified_strategy(
            build_certified_strategy()
        )
    )


    stored = registry.get(
        "STR-001"
    )


    assert stored == result


def test_registry_keeps_certification_data():

    registry = StrategyRegistryV2()

    service = (
        StrategyCertificationRegistryServiceV2(
            registry=registry,
        )
    )


    service.register_certified_strategy(
        build_certified_strategy()
    )


    strategy = registry.get(
        "STR-001"
    )


    assert strategy["grade"] == "A"
    assert strategy["status"] == "CERTIFIED"
