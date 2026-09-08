from pathlib import Path

import pytest

from backend.config_settings import ArmsSettings


def test_arms_settings_owns_exposure_policy_defaults():
    settings = ArmsSettings()

    assert settings.maximum_total_open_risk == 500.0
    assert settings.maximum_symbol_open_risk == 300.0

    assert settings.maximum_portfolio_open_risk == 1000.0
    assert settings.maximum_portfolio_floating_loss == 600.0
    assert settings.maximum_portfolio_long_risk == 700.0
    assert settings.maximum_portfolio_short_risk == 700.0
    assert settings.maximum_portfolio_symbol_risk == 500.0


def test_exposure_policy_values_must_be_positive():
    fields = (
        "maximum_total_open_risk",
        "maximum_symbol_open_risk",
        "maximum_portfolio_open_risk",
        "maximum_portfolio_floating_loss",
        "maximum_portfolio_long_risk",
        "maximum_portfolio_short_risk",
        "maximum_portfolio_symbol_risk",
    )

    for field in fields:
        with pytest.raises(ValueError):
            ArmsSettings(**{field: 0.0})


def test_exposure_policy_relational_invariants():
    with pytest.raises(ValueError):
        ArmsSettings(
            maximum_total_open_risk=200.0,
            maximum_symbol_open_risk=300.0,
        )

    with pytest.raises(ValueError):
        ArmsSettings(
            maximum_portfolio_open_risk=500.0,
            maximum_portfolio_long_risk=600.0,
        )

    with pytest.raises(ValueError):
        ArmsSettings(
            maximum_portfolio_open_risk=500.0,
            maximum_portfolio_short_risk=600.0,
        )

    with pytest.raises(ValueError):
        ArmsSettings(
            maximum_portfolio_open_risk=500.0,
            maximum_portfolio_symbol_risk=600.0,
        )


def test_create_app_wires_exposure_policy_from_canonical_settings():
    source = Path(
        "backend/api/app.py"
    ).read_text(
        encoding="utf-8",
        errors="replace",
    )

    compact = "".join(
        source.split()
    )

    required = (
        "internal_policy_settings.maximum_total_open_risk",
        "internal_policy_settings.maximum_symbol_open_risk",
        "internal_policy_settings.maximum_portfolio_open_risk",
        "internal_policy_settings.maximum_portfolio_floating_loss",
        "internal_policy_settings.maximum_portfolio_long_risk",
        "internal_policy_settings.maximum_portfolio_short_risk",
        "internal_policy_settings.maximum_portfolio_symbol_risk",
    )

    for expression in required:
        assert expression in compact


def test_create_app_removes_seven_exposure_policy_literals():
    compact = Path(
        "backend/api/app.py"
    ).read_text(
        encoding="utf-8",
        errors="replace",
    ).replace(" ", "")

    forbidden = (
        "maximum_total_open_risk=500.0",
        "maximum_symbol_open_risk=300.0",
        "maximum_total_open_risk=1000.0",
        "maximum_floating_loss=600.0",
        "maximum_long_risk=700.0",
        "maximum_short_risk=700.0",
        "maximum_symbol_risk=500.0",
    )

    for expression in forbidden:
        assert expression not in compact
