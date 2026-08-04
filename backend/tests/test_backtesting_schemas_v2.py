import pytest
from pydantic import ValidationError

from backend.api.schemas.backtesting import (
    BacktestingCandleRequest,
    BacktestingRunRequest,
)


def valid_candle():

    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "timestamp": "2026-08-04T09:30:00Z",
        "open": 21000.0,
        "high": 21010.0,
        "low": 20995.0,
        "close": 21005.0,
        "volume": 1500.0,
    }


def test_accepts_valid_backtesting_request():

    request = BacktestingRunRequest(
        candles=[
            valid_candle(),
            {
                **valid_candle(),
                "timestamp": (
                    "2026-08-04T09:35:00Z"
                ),
                "open": 21005.0,
                "high": 21020.0,
                "low": 21000.0,
                "close": 21015.0,
            },
        ],
        output_directory=(
            "reports/backtesting"
        ),
    )

    assert len(request.candles) == 2

    assert isinstance(
        request.candles[0],
        BacktestingCandleRequest,
    )

    assert (
        request.output_directory
        == "reports/backtesting"
    )


def test_rejects_empty_candle_list():

    with pytest.raises(
        ValidationError,
    ):
        BacktestingRunRequest(
            candles=[],
        )


def test_rejects_invalid_ohlc_relationship():

    candle = valid_candle()

    candle["high"] = 20900.0

    with pytest.raises(
        ValidationError,
    ):
        BacktestingRunRequest(
            candles=[candle],
        )


def test_rejects_negative_volume():

    candle = valid_candle()

    candle["volume"] = -1.0

    with pytest.raises(
        ValidationError,
    ):
        BacktestingRunRequest(
            candles=[candle],
        )


def test_uses_default_output_directory():

    request = BacktestingRunRequest(
        candles=[
            valid_candle(),
        ],
    )

    assert (
        request.output_directory
        == "reports/backtesting"
    )
