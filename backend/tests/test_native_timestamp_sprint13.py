"""Synthetic clock/boundary regression; never replay native evidence for admission."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.tests.test_ninjatrader_market_sprint11 import setup, hello, bar, send, api_settings
from backend.market_data.ninjatrader_market_reader_v1 import _utc

UTC = timezone.utc
START = datetime(2026, 9, 21, 0, 23, tzinfo=UTC)


@pytest.mark.parametrize("offset", [-1.178974, -0.994520, -1.195736, -1.232827, -0.276106, -0.000001])
def test_prestart_forming_rejected_without_runtime_or_bookkeeping(api_settings, tmp_path, offset):
    r, clock = setup(tmp_path, start=START + timedelta(seconds=offset) - timedelta(minutes=1))
    clock[0] = START + timedelta(seconds=offset)
    send(r, hello(r, clock))
    with pytest.raises(ValueError, match="TRANSPORT_RECOVERY_REQUIRED"):
        send(r, bar(clock, 1, "FORMING", bar_time=(START+timedelta(minutes=1)).isoformat()))
    assert r.service._runtime is None
    assert r.service.gate.closed_count == 0
    assert not (tmp_path / "paper.sqlite").exists()
    assert r.get_snapshot()["external_order_authority"] is False
    r.close()


@pytest.mark.parametrize("offset", [0, .000001, .2, 30, 59.999999])
def test_future_close_label_is_valid_metadata_during_forming_minute(api_settings, tmp_path, offset):
    r, clock = setup(tmp_path, start=START + timedelta(seconds=offset) - timedelta(minutes=1))
    clock[0] = START + timedelta(seconds=offset)
    send(r, hello(r, clock))
    result = send(r, bar(clock, 1, "FORMING", bar_time=(START+timedelta(minutes=1)).isoformat()))
    assert result["market_data"]["status"] == "FORMING_CANDLE"
    assert r.service._runtime is None
    assert result["market_data"]["closed_candles"] == 0
    assert not result["external_order_authority"]
    r.close()


@pytest.mark.parametrize("future_seconds", [.000001, 1.178974, 60])
def test_genuinely_future_closed_candle_never_initializes_account(api_settings, tmp_path, future_seconds):
    r, clock = setup(tmp_path, start=START - timedelta(seconds=future_seconds) - timedelta(minutes=1))
    clock[0] = START - timedelta(seconds=future_seconds)
    send(r, hello(r, clock))
    with pytest.raises(ValueError):
        send(r, bar(clock, 1, "CLOSED", bar_time=START.isoformat()))
    assert r.service._runtime is None and r.service.gate.closed_count == 0
    assert not (tmp_path / "paper.sqlite").exists()
    r.close()


def test_future_emission_rejected_even_with_valid_forming_label(api_settings, tmp_path):
    r, clock = setup(tmp_path, start=START - timedelta(minutes=1))
    clock[0] = START
    send(r, hello(r, clock))
    f = bar(clock, 1, "FORMING", bar_time=(START+timedelta(minutes=1)).isoformat())
    f["event_time"] = (START+timedelta(microseconds=1)).isoformat()
    with pytest.raises(ValueError):
        send(r, f)
    assert r.service._runtime is None and r.service.gate.closed_count == 0
    r.close()


def test_observed_normalization_preserves_boundary_instead_of_shifting_seconds():
    emitted = _utc("2026-09-21T00:22:58.8210269Z")
    close = _utc("2026-09-21T00:24:00.0000000Z")
    assert close == START+timedelta(minutes=1)
    assert (emitted-(close-timedelta(minutes=1))).total_seconds() == -1.178974
    assert _utc("2026-09-21T00:24:00+00:00") == close
    with pytest.raises(ValueError):
        _utc("2026-09-20T20:24:00-04:00")
