
import pytest

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


def test_register_certified_strategy():

    registry = StrategyRegistryV2()

    service = (
        StrategyCertificationRegistryServiceV2(
            registry=registry,
        )
    )


    result = service.register_certified_strategy(
        build_certified_strategy()
    )


    assert result["status"] == (
        "CERTIFIED"
    )


    stored = registry.get(
        "STR-001"
    )


    assert stored["grade"] == "A"


def test_reject_non_certified_strategy():

    registry = StrategyRegistryV2()

    service = (
        StrategyCertificationRegistryServiceV2(
            registry=registry,
        )
    )


    with pytest.raises(
        ValueError,
    ):

        service.register_certified_strategy(
            {
                "strategy_id": "STR-002",
                "status": "PROVISIONAL",
            }
        )


def test_invalid_registry_rejected():

    with pytest.raises(
        TypeError,
    ):

        StrategyCertificationRegistryServiceV2(
            registry=object(),
        )
