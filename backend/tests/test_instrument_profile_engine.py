import pytest

from backend.instruments.instrument_profile_engine import (
    InstrumentProfileEngine,
)


def build_engine() -> InstrumentProfileEngine:
    return InstrumentProfileEngine()


def test_returns_mnq_profile():
    engine = build_engine()

    result = engine.get_profile(
        symbol="MNQ"
    )

    assert result["symbol"] == "MNQ"
    assert result["name"] == "Micro E-mini Nasdaq-100"
    assert result["point_value"] == 2.0
    assert result["tick_size"] == 0.25
    assert result["tick_value"] == 0.50
    assert result["maximum_contracts"] == 20


def test_returns_nq_profile():
    engine = build_engine()

    result = engine.get_profile(
        symbol="NQ"
    )

    assert result["symbol"] == "NQ"
    assert result["name"] == "E-mini Nasdaq-100"
    assert result["point_value"] == 20.0
    assert result["tick_size"] == 0.25
    assert result["tick_value"] == 5.0
    assert result["maximum_contracts"] == 5


def test_returns_mes_profile():
    engine = build_engine()

    result = engine.get_profile(
        symbol="MES"
    )

    assert result["symbol"] == "MES"
    assert result["name"] == "Micro E-mini S&P 500"
    assert result["point_value"] == 5.0
    assert result["tick_size"] == 0.25
    assert result["tick_value"] == 1.25
    assert result["maximum_contracts"] == 20


def test_returns_es_profile():
    engine = build_engine()

    result = engine.get_profile(
        symbol="ES"
    )

    assert result["symbol"] == "ES"
    assert result["name"] == "E-mini S&P 500"
    assert result["point_value"] == 50.0
    assert result["tick_size"] == 0.25
    assert result["tick_value"] == 12.50
    assert result["maximum_contracts"] == 5


def test_normalizes_symbol():
    engine = build_engine()

    result = engine.get_profile(
        symbol="  mnq  "
    )

    assert result["symbol"] == "MNQ"


def test_returns_defensive_copy():
    engine = build_engine()

    first = engine.get_profile(
        symbol="MNQ"
    )

    first["point_value"] = 999.0

    second = engine.get_profile(
        symbol="MNQ"
    )

    assert second["point_value"] == 2.0


def test_checks_supported_symbol():
    engine = build_engine()

    assert (
        engine.is_supported(
            symbol="NQ"
        )
        is True
    )

    assert (
        engine.is_supported(
            symbol="UNKNOWN"
        )
        is False
    )


def test_lists_supported_symbols():
    engine = build_engine()

    result = engine.list_symbols()

    assert result == [
        "ES",
        "MES",
        "MNQ",
        "NQ",
    ]


def test_rejects_empty_symbol():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        engine.get_profile(
            symbol="   "
        )


def test_rejects_unsupported_symbol():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="soportado",
    ):
        engine.get_profile(
            symbol="YM"
        )


def test_mnq_is_micro_contract():
    engine = build_engine()

    result = engine.get_profile(
        symbol="MNQ"
    )

    assert result["contract_class"] == "MICRO"
    assert result["family"] == "NASDAQ_100"


def test_nq_is_mini_contract():
    engine = build_engine()

    result = engine.get_profile(
        symbol="NQ"
    )

    assert result["contract_class"] == "MINI"
    assert result["family"] == "NASDAQ_100"


def test_mes_is_micro_contract():
    engine = build_engine()

    result = engine.get_profile(
        symbol="MES"
    )

    assert result["contract_class"] == "MICRO"
    assert result["family"] == "SP500"


def test_es_is_mini_contract():
    engine = build_engine()

    result = engine.get_profile(
        symbol="ES"
    )

    assert result["contract_class"] == "MINI"
    assert result["family"] == "SP500"


def test_contract_caps_are_classified_as_legacy_safety_caps():
    engine = build_engine()

    for symbol in (
        "NQ",
        "MNQ",
        "ES",
        "MES",
    ):
        profile = engine.get_profile(
            symbol=symbol
        )

        assert (
            profile["contract_limit_source"]
            == "LEGACY_SAFETY_CAP"
        )


def test_micro_profile_legacy_cap_is_not_active_account_limit():
    from backend.accounts.account_config_manager_v2 import (
        AccountConfigManagerV2,
    )

    engine = build_engine()

    account = (
        AccountConfigManagerV2()
        .get_active_account()
    )

    mnq = engine.get_profile(
        symbol="MNQ"
    )

    mes = engine.get_profile(
        symbol="MES"
    )

    assert mnq["maximum_contracts"] == 20
    assert mes["maximum_contracts"] == 20

    assert (
        account.get_contract_limit(
            mnq["contract_class"]
        )
        == 150
    )

    assert (
        account.get_contract_limit(
            mes["contract_class"]
        )
        == 150
    )


def test_mini_profile_legacy_cap_matches_current_account_by_coincidence():
    from backend.accounts.account_config_manager_v2 import (
        AccountConfigManagerV2,
    )

    engine = build_engine()

    account = (
        AccountConfigManagerV2()
        .get_active_account()
    )

    for symbol in (
        "NQ",
        "ES",
    ):
        profile = engine.get_profile(
            symbol=symbol
        )

        assert profile["maximum_contracts"] == 5

        assert (
            account.get_contract_limit(
                profile["contract_class"]
            )
            == 15
        )

        assert (
            profile["contract_limit_source"]
            == "LEGACY_SAFETY_CAP"
        )
