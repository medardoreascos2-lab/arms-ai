from backend.config_settings import ArmsSettings


def test_default_settings_are_valid():
    settings = ArmsSettings()

    assert settings.provider == "SIMULATED"
    assert settings.symbol == "NASDAQ / NQ"
    assert settings.timeframe == "1m"

    assert settings.candle_limit >= 50
    assert settings.max_candles >= settings.candle_limit

    assert settings.account_balance > 0
    assert 0 < settings.risk_percent <= 100
    assert settings.point_value > 0

    assert settings.ema_period > 0
    assert settings.rsi_period > 0
    assert settings.atr_period > 0


def test_settings_allow_custom_values():
    settings = ArmsSettings(
        provider="CUSTOM",
        symbol="ES",
        timeframe="5m",
        account_balance=25000,
        risk_percent=1.0,
    )

    assert settings.provider == "CUSTOM"
    assert settings.symbol == "ES"
    assert settings.timeframe == "5m"
    assert settings.account_balance == 25000
    assert settings.risk_percent == 1.0


def test_settings_reject_invalid_risk_percent():
    try:
        ArmsSettings(risk_percent=0)
    except ValueError as error:
        assert "risk_percent" in str(error)
    else:
        raise AssertionError(
            "ArmsSettings debía rechazar risk_percent=0."
        )
