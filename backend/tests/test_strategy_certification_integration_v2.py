from backend.api.app import create_app


def build_certified_strategy():

    return {
        "strategy_id": "STR-CERT-001",
        "name": "EMA50 Smart Money",
        "version": "1.0",
        "status": "CERTIFIED",
        "grade": "A",
        "validation_score": 95,
        "performance_score": 90,
    }



def test_certification_registers_strategy():

    app = create_app()

    registry = (
        app.state
        .strategy_registry_v2
    )


    certification_service = (
        app.state
        .strategy_certification_registry_service_v2
    )


    result = (
        certification_service
        .register_certified_strategy(
            build_certified_strategy()
        )
    )


    assert result["status"] == "CERTIFIED"


    strategies = (
        registry.list()
    )


    assert len(
        strategies
    ) == 1


    assert strategies[0][
        "strategy_id"
    ] == "STR-CERT-001"
