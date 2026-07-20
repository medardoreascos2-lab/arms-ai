import pandas as pd
import pytest

from backend.services.market_data import (
    download_prices,
)


def test_download_prices_returns_multiple_symbols(
    monkeypatch,
):
    columns = pd.MultiIndex.from_product(
        [
            ["Close"],
            ["AAPL", "MSFT"],
        ]
    )

    downloaded = pd.DataFrame(
        [
            [100.0, 200.0],
            [101.0, 202.0],
        ],
        columns=columns,
    )

    monkeypatch.setattr(
        "backend.services.market_data.yf.download",
        lambda *args, **kwargs: downloaded,
    )

    result = download_prices(
        ["AAPL", "MSFT"],
    )

    assert list(result.columns) == [
        "AAPL",
        "MSFT",
    ]
    assert len(result) == 2


def test_download_prices_returns_single_symbol(
    monkeypatch,
):
    downloaded = pd.DataFrame(
        {
            "Close": [
                100.0,
                101.0,
            ],
        }
    )

    monkeypatch.setattr(
        "backend.services.market_data.yf.download",
        lambda *args, **kwargs: downloaded,
    )

    result = download_prices(
        ["AAPL"],
    )

    assert list(result.columns) == [
        "AAPL",
    ]


def test_download_prices_normalizes_symbols(
    monkeypatch,
):
    captured = {}

    downloaded = pd.DataFrame(
        {
            "Close": [
                100.0,
                101.0,
            ],
        }
    )

    def fake_download(
        symbols,
        **kwargs,
    ):
        captured["symbols"] = symbols
        return downloaded

    monkeypatch.setattr(
        "backend.services.market_data.yf.download",
        fake_download,
    )

    download_prices(
        [" aapl "],
    )

    assert captured["symbols"] == [
        "AAPL",
    ]


def test_download_prices_rejects_empty_symbols():
    with pytest.raises(
        ValueError,
        match="symbols",
    ):
        download_prices([])


def test_download_prices_rejects_empty_data(
    monkeypatch,
):
    monkeypatch.setattr(
        "backend.services.market_data.yf.download",
        lambda *args, **kwargs: pd.DataFrame(),
    )

    with pytest.raises(
        ValueError,
        match="precios",
    ):
        download_prices(
            ["AAPL"],
        )
