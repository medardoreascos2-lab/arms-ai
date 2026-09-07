from __future__ import annotations

import math

import pytest


def _authority_class():
    from backend.services.spread_authority_v2 import (
        SpreadAuthorityV2,
    )

    return SpreadAuthorityV2


def test_spread_authority_calculates_runtime_bid_ask_spread() -> None:
    authority_class = _authority_class()
    authority = authority_class()

    result = authority.resolve_spread_points(
        symbol="NQ",
        bid=22000.25,
        ask=22000.75,
    )

    assert result == pytest.approx(0.50)


def test_spread_authority_does_not_use_tick_size_as_spread() -> None:
    authority_class = _authority_class()
    authority = authority_class()

    result = authority.resolve_spread_points(
        symbol="NQ",
        bid=22000.00,
        ask=22001.00,
    )

    assert result == pytest.approx(1.00)
    assert result != pytest.approx(0.25)


@pytest.mark.parametrize(
    ("bid", "ask"),
    [
        (None, 22000.50),
        (22000.25, None),
        (None, None),
    ],
)
def test_spread_authority_fails_closed_without_complete_quote(
    bid,
    ask,
) -> None:
    authority_class = _authority_class()
    authority = authority_class()

    with pytest.raises(
        (ValueError, RuntimeError),
    ):
        authority.resolve_spread_points(
            symbol="NQ",
            bid=bid,
            ask=ask,
        )


@pytest.mark.parametrize(
    ("bid", "ask"),
    [
        (0.0, 22000.50),
        (-1.0, 22000.50),
        (22000.25, 0.0),
        (22000.25, -1.0),
        (math.nan, 22000.50),
        (22000.25, math.nan),
        (math.inf, 22000.50),
        (22000.25, math.inf),
    ],
)
def test_spread_authority_rejects_invalid_quote_values(
    bid,
    ask,
) -> None:
    authority_class = _authority_class()
    authority = authority_class()

    with pytest.raises(ValueError):
        authority.resolve_spread_points(
            symbol="NQ",
            bid=bid,
            ask=ask,
        )


def test_spread_authority_rejects_crossed_quote() -> None:
    authority_class = _authority_class()
    authority = authority_class()

    with pytest.raises(ValueError):
        authority.resolve_spread_points(
            symbol="NQ",
            bid=22001.00,
            ask=22000.75,
        )


def test_spread_authority_accepts_locked_quote_as_zero_spread() -> None:
    authority_class = _authority_class()
    authority = authority_class()

    result = authority.resolve_spread_points(
        symbol="NQ",
        bid=22000.25,
        ask=22000.25,
    )

    assert result == pytest.approx(0.0)


def test_spread_authority_normalizes_symbol() -> None:
    authority_class = _authority_class()
    authority = authority_class()

    result = authority.resolve_spread_points(
        symbol=" nq ",
        bid=22000.25,
        ask=22000.50,
    )

    assert result == pytest.approx(0.25)


def test_spread_authority_rejects_empty_symbol() -> None:
    authority_class = _authority_class()
    authority = authority_class()

    with pytest.raises(ValueError):
        authority.resolve_spread_points(
            symbol="",
            bid=22000.25,
            ask=22000.50,
        )
