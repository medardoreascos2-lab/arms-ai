from backend.api.app import create_app
from backend.services.certified_market_hours_runtime_provider_v2 import (
    CertifiedMarketHoursRuntimeProviderV2,
)
from backend.services.market_hours_service_v2 import (
    MarketHoursServiceV2,
)


def test_app_exposes_certified_market_hours_provider():
    app = create_app()

    provider = (
        app.state
        .market_hours_runtime_provider_v2
    )

    assert isinstance(
        provider,
        CertifiedMarketHoursRuntimeProviderV2,
    )


def test_app_exposes_market_hours_service_v2():
    app = create_app()

    assert isinstance(
        app.state.market_hours_service_v2,
        MarketHoursServiceV2,
    )


def test_app_market_hours_service_is_provider_owned():
    app = create_app()

    provider = (
        app.state
        .market_hours_runtime_provider_v2
    )

    assert (
        app.state.market_hours_service_v2
        is provider.get_market_hours_service()
    )
