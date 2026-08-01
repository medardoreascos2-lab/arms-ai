from datetime import datetime

import pytest

from backend.backtesting.csv_candle_loader_v2 import (
    CsvCandleLoaderV2,
)
from backend.models.candle import Candle


def write_csv(
    tmp_path,
    content: str,
):
    path = tmp_path / "candles.csv"
    path.write_text(
        content,
        encoding="utf-8",
    )
    return path


def test_loads_valid_csv_as_candles(tmp_path):

    csv_path = write_csv(
        tmp_path,
        (
            "timestamp,open,high,low,close,volume\n"
            "2026-01-01T09:31:00,101,102,100,101.5,1200\n"
            "2026-01-01T09:30:00,100,101,99,100.5,1000\n"
        ),
    )

    loader = CsvCandleLoaderV2(
        csv_path=csv_path,
        symbol="nq",
        timeframe="5M",
    )

    candles = loader.load()

    assert len(candles) == 2

    assert all(
        isinstance(candle, Candle)
        for candle in candles
    )

    assert candles[0].timestamp == datetime(
        2026,
        1,
        1,
        9,
        30,
    )

    assert candles[1].timestamp == datetime(
        2026,
        1,
        1,
        9,
        31,
    )

    assert candles[0].symbol == "NQ"
    assert candles[0].timeframe == "5m"

    assert candles[0].open == 100.0
    assert candles[0].high == 101.0
    assert candles[0].low == 99.0
    assert candles[0].close == 100.5
    assert candles[0].volume == 1000.0


def test_rejects_empty_csv(tmp_path):

    csv_path = write_csv(
        tmp_path,
        "",
    )

    loader = CsvCandleLoaderV2(
        csv_path=csv_path,
        symbol="NQ",
        timeframe="5m",
    )

    with pytest.raises(
        ValueError,
        match="vacío",
    ):
        loader.load()


@pytest.mark.parametrize(
    "missing_column",
    [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ],
)
def test_rejects_missing_required_column(
    tmp_path,
    missing_column,
):

    columns = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    remaining_columns = [
        column
        for column in columns
        if column != missing_column
    ]

    values = {
        "timestamp": "2026-01-01T09:30:00",
        "open": "100",
        "high": "101",
        "low": "99",
        "close": "100.5",
        "volume": "1000",
    }

    csv_path = write_csv(
        tmp_path,
        (
            ",".join(remaining_columns)
            + "\n"
            + ",".join(
                values[column]
                for column in remaining_columns
            )
            + "\n"
        ),
    )

    loader = CsvCandleLoaderV2(
        csv_path=csv_path,
        symbol="NQ",
        timeframe="5m",
    )

    with pytest.raises(
        ValueError,
        match=missing_column,
    ):
        loader.load()


def test_rejects_invalid_timestamp(tmp_path):

    csv_path = write_csv(
        tmp_path,
        (
            "timestamp,open,high,low,close,volume\n"
            "INVALID,100,101,99,100.5,1000\n"
        ),
    )

    loader = CsvCandleLoaderV2(
        csv_path=csv_path,
        symbol="NQ",
        timeframe="5m",
    )

    with pytest.raises(
        ValueError,
        match="timestamp",
    ):
        loader.load()


def test_rejects_invalid_numeric_value(tmp_path):

    csv_path = write_csv(
        tmp_path,
        (
            "timestamp,open,high,low,close,volume\n"
            "2026-01-01T09:30:00,INVALID,101,99,100.5,1000\n"
        ),
    )

    loader = CsvCandleLoaderV2(
        csv_path=csv_path,
        symbol="NQ",
        timeframe="5m",
    )

    with pytest.raises(
        ValueError,
        match="open",
    ):
        loader.load()


def test_rejects_invalid_ohlc_relationship(tmp_path):

    csv_path = write_csv(
        tmp_path,
        (
            "timestamp,open,high,low,close,volume\n"
            "2026-01-01T09:30:00,100,98,99,100.5,1000\n"
        ),
    )

    loader = CsvCandleLoaderV2(
        csv_path=csv_path,
        symbol="NQ",
        timeframe="5m",
    )

    with pytest.raises(
        ValueError,
        match="OHLC",
    ):
        loader.load()


def test_rejects_missing_file(tmp_path):

    loader = CsvCandleLoaderV2(
        csv_path=(
            tmp_path
            / "missing.csv"
        ),
        symbol="NQ",
        timeframe="5m",
    )

    with pytest.raises(
        FileNotFoundError,
    ):
        loader.load()


def test_rejects_empty_symbol(tmp_path):

    csv_path = write_csv(
        tmp_path,
        (
            "timestamp,open,high,low,close,volume\n"
            "2026-01-01T09:30:00,100,101,99,100.5,1000\n"
        ),
    )

    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        CsvCandleLoaderV2(
            csv_path=csv_path,
            symbol="   ",
            timeframe="5m",
        )


def test_rejects_empty_timeframe(tmp_path):

    csv_path = write_csv(
        tmp_path,
        (
            "timestamp,open,high,low,close,volume\n"
            "2026-01-01T09:30:00,100,101,99,100.5,1000\n"
        ),
    )

    with pytest.raises(
        ValueError,
        match="timeframe",
    ):
        CsvCandleLoaderV2(
            csv_path=csv_path,
            symbol="NQ",
            timeframe="   ",
        )
