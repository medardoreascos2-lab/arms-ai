from __future__ import annotations

import pytest

from backend.config.api_settings import APISettings


ENV_NAME = "ARMS_CERTIFIED_ECONOMIC_NEWS_PATH"


def test_certified_economic_news_path_is_dataclass_field():
    assert (
        "certified_economic_news_path"
        in APISettings.__dataclass_fields__
    )


def test_certified_economic_news_path_defaults_to_none(
    monkeypatch,
):
    monkeypatch.delenv(
        ENV_NAME,
        raising=False,
    )

    settings = APISettings()

    assert (
        settings.certified_economic_news_path
        is None
    )


def test_certified_economic_news_path_uses_environment(
    monkeypatch,
    tmp_path,
):
    path = (
        tmp_path
        / "certified-economic-news.json"
    )

    monkeypatch.setenv(
        ENV_NAME,
        str(path),
    )

    settings = APISettings()

    assert (
        settings.certified_economic_news_path
        == str(path)
    )


def test_certified_economic_news_path_blank_environment_is_none(
    monkeypatch,
):
    monkeypatch.setenv(
        ENV_NAME,
        "   ",
    )

    settings = APISettings()

    assert (
        settings.certified_economic_news_path
        is None
    )


def test_certified_economic_news_path_normalizes_explicit_value():
    settings = APISettings(
        certified_economic_news_path=(
            "  /tmp/certified-economic-news.json  "
        ),
    )

    assert (
        settings.certified_economic_news_path
        == "/tmp/certified-economic-news.json"
    )


def test_certified_economic_news_path_explicit_blank_is_none():
    settings = APISettings(
        certified_economic_news_path="   ",
    )

    assert (
        settings.certified_economic_news_path
        is None
    )


def test_certified_economic_news_path_rejects_invalid_type():
    assert (
        "certified_economic_news_path"
        in APISettings.__dataclass_fields__
    )

    with pytest.raises(
        TypeError,
        match="certified_economic_news_path",
    ):
        APISettings(
            certified_economic_news_path=object(),
        )
