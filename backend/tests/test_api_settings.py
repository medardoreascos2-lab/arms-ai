from backend.config.api_settings import (
    APISettings,
)


def test_default_title():
    settings = APISettings()

    assert settings.title == "ARMS AI API"


def test_default_version():
    settings = APISettings()

    assert settings.version == "1.0.0"


def test_default_host():
    settings = APISettings()

    assert settings.host == "127.0.0.1"


def test_default_port():
    settings = APISettings()

    assert settings.port == 8000


def test_default_debug():
    settings = APISettings()

    assert settings.debug is False



def test_certified_market_hours_path_defaults_to_none(
    monkeypatch,
):
    monkeypatch.delenv(
        "ARMS_CERTIFIED_MARKET_HOURS_PATH",
        raising=False,
    )

    settings = APISettings()

    assert settings.certified_market_hours_path is None


def test_certified_market_hours_path_uses_environment(
    monkeypatch,
    tmp_path,
):
    configured_path = (
        tmp_path / "certified-market-hours.json"
    )

    monkeypatch.setenv(
        "ARMS_CERTIFIED_MARKET_HOURS_PATH",
        str(configured_path),
    )

    settings = APISettings()

    assert settings.certified_market_hours_path == (
        str(configured_path)
    )


def test_certified_market_hours_path_blank_environment_is_none(
    monkeypatch,
):
    monkeypatch.setenv(
        "ARMS_CERTIFIED_MARKET_HOURS_PATH",
        "   ",
    )

    settings = APISettings()

    assert settings.certified_market_hours_path is None


def test_certified_market_hours_path_normalizes_explicit_value():
    settings = APISettings(
        certified_market_hours_path=(
            "  /tmp/certified-hours.json  "
        ),
    )

    assert settings.certified_market_hours_path == (
        "/tmp/certified-hours.json"
    )


def test_certified_market_hours_path_explicit_blank_is_none():
    settings = APISettings(
        certified_market_hours_path="   ",
    )

    assert settings.certified_market_hours_path is None


def test_certified_market_hours_path_rejects_invalid_type():
    import pytest

    with pytest.raises(
        TypeError,
        match="certified_market_hours_path",
    ):
        APISettings(
            certified_market_hours_path=object(),
        )
