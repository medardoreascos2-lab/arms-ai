from datetime import datetime, timezone

from backend.market_data.external_market_data_provider_v2 import (
    ExternalMarketDataProviderV2,
    ExternalMarketDataQuoteV2,
)


class FakeExternalMarketDataProviderV2:
    @property
    def provider_name(self) -> str:
        return "FAKE"

    def get_quote(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> ExternalMarketDataQuoteV2:
        return ExternalMarketDataQuoteV2(
            symbol=symbol,
            price=22000.0,
            source=self.provider_name,
            timeframe=timeframe,
            timestamp=datetime(
                2026,
                9,
                15,
                20,
                0,
                tzinfo=timezone.utc,
            ),
        )


def test_external_market_data_quote_is_immutable():
    quote = FakeExternalMarketDataProviderV2().get_quote(
        symbol="NQ",
        timeframe="1M",
    )

    assert quote.symbol == "NQ"
    assert quote.price == 22000.0
    assert quote.source == "FAKE"
    assert quote.timeframe == "1M"
    assert quote.timestamp.tzinfo is not None


def test_concrete_provider_satisfies_runtime_boundary():
    provider = FakeExternalMarketDataProviderV2()

    assert isinstance(
        provider,
        ExternalMarketDataProviderV2,
    )


def test_provider_returns_canonical_quote_contract():
    provider = FakeExternalMarketDataProviderV2()

    quote = provider.get_quote(
        symbol="MNQ",
        timeframe="5M",
    )

    assert isinstance(quote, ExternalMarketDataQuoteV2)
    assert quote.symbol == "MNQ"
    assert quote.timeframe == "5M"
    assert quote.source == provider.provider_name



def test_price_feed_can_pull_from_external_provider():
    from backend.services.price_feed_service_v2 import (
        PriceFeedServiceV2,
    )

    provider = FakeExternalMarketDataProviderV2()

    service = PriceFeedServiceV2(
        external_market_data_provider_v2=provider,
    )

    result = service.pull_external_quote(
        symbol="NQ",
        timeframe="1M",
    )

    assert result["processed"] is True
    assert result["symbol"] == "NQ"
    assert result["current_price"] == 22000.0
    assert result["source"] == "FAKE"


def test_price_feed_external_pull_fails_closed_without_provider():
    import pytest

    from backend.services.price_feed_service_v2 import (
        PriceFeedServiceV2,
    )

    service = PriceFeedServiceV2()

    with pytest.raises(
        RuntimeError,
        match="provider no configurado",
    ):
        service.pull_external_quote(
            symbol="NQ",
            timeframe="1M",
        )


def test_price_feed_rejects_invalid_external_provider():
    import pytest

    from backend.services.price_feed_service_v2 import (
        PriceFeedServiceV2,
    )

    with pytest.raises(
        TypeError,
        match="external_market_data_provider_v2",
    ):
        PriceFeedServiceV2(
            external_market_data_provider_v2=object(),
        )
