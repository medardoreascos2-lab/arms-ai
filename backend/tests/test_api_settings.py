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
