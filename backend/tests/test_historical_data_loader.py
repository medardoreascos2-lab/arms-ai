from pathlib import Path

import pytest

from backend.backtesting.historical_data_loader import (
    HistoricalDataLoader,
)


def test_loader_reads_candles_from_csv(tmp_path):
    file_path = tmp_path / "candles.csv"

    file_path.write_text(
        "\n".join(
            [
                (
                    "timestamp,symbol,timeframe,open,high,"
                    "low,close,volume"
                ),
                (
                    "2026-01-01T09:30:00,TEST,1m,"
                    "100.0,101.0,99.5,100.5,1000"
                ),
                (
                    "2026-01-01T09:31:00,TEST,1m,"
                    "100.5,102.0,100.0,101.5,1200"
                ),
            ]
        ),
        encoding="utf-8",
    )

    loader = HistoricalDataLoader()

    candles = loader.load_csv(
        file_path=file_path,
    )

    assert len(candles) == 2

    first = candles[0]

    assert first.symbol == "TEST"
    assert first.timeframe == "1m"
    assert first.open == 100.0
    assert first.high == 101.0
    assert first.low == 99.5
    assert first.close == 100.5
    assert first.volume == 1000


def test_loader_sorts_candles_by_timestamp(tmp_path):
    file_path = tmp_path / "candles.csv"

    file_path.write_text(
        "\n".join(
            [
                (
                    "timestamp,symbol,timeframe,open,high,"
                    "low,close,volume"
                ),
                (
                    "2026-01-01T09:31:00,TEST,1m,"
                    "100.5,102.0,100.0,101.5,1200"
                ),
                (
                    "2026-01-01T09:30:00,TEST,1m,"
                    "100.0,101.0,99.5,100.5,1000"
                ),
            ]
        ),
        encoding="utf-8",
    )

    candles = HistoricalDataLoader().load_csv(
        file_path=file_path,
    )

    assert candles[0].timestamp < candles[1].timestamp


def test_loader_rejects_missing_file(tmp_path):
    loader = HistoricalDataLoader()

    with pytest.raises(
        FileNotFoundError,
    ):
        loader.load_csv(
            file_path=tmp_path / "missing.csv",
        )


def test_loader_rejects_empty_csv(tmp_path):
    file_path = tmp_path / "empty.csv"
    file_path.write_text(
        "timestamp,symbol,timeframe,open,high,low,close,volume\n",
        encoding="utf-8",
    )

    loader = HistoricalDataLoader()

    with pytest.raises(
        ValueError,
        match="velas",
    ):
        loader.load_csv(
            file_path=file_path,
        )


def test_loader_rejects_missing_columns(tmp_path):
    file_path = tmp_path / "invalid.csv"

    file_path.write_text(
        "\n".join(
            [
                "timestamp,symbol,close",
                "2026-01-01T09:30:00,TEST,100.5",
            ]
        ),
        encoding="utf-8",
    )

    loader = HistoricalDataLoader()

    with pytest.raises(
        ValueError,
        match="columnas",
    ):
        loader.load_csv(
            file_path=file_path,
        )
