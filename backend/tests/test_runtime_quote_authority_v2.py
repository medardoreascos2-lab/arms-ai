from __future__ import annotations

import importlib
from datetime import datetime, timezone

import pytest


MODULE_NAME = "backend.services.runtime_quote_authority_v2"


def _load_runtime_quote_authority_class():
    module = importlib.import_module(MODULE_NAME)

    authority_class = getattr(
        module,
        "RuntimeQuoteAuthorityV2",
    )

    return authority_class


def _build_authority():
    authority_class = (
        _load_runtime_quote_authority_class()
    )

    return authority_class()


def test_runtime_quote_authority_module_exists() -> None:
    module = importlib.import_module(
        MODULE_NAME
    )

    assert hasattr(
        module,
        "RuntimeQuoteAuthorityV2",
    )


def test_runtime_quote_authority_accepts_bid_and_ask() -> None:
    authority = _build_authority()

    timestamp = datetime(
        2026,
        9,
        7,
        14,
        30,
        tzinfo=timezone.utc,
    )

    authority.publish_quote(
        symbol="NQ",
        bid=25000.25,
        ask=25000.75,
        timestamp=timestamp,
    )

    quote = authority.get_quote(
        symbol="NQ",
    )

    assert quote is not None
    assert quote["symbol"] == "NQ"
    assert quote["bid"] == pytest.approx(
        25000.25
    )
    assert quote["ask"] == pytest.approx(
        25000.75
    )
    assert quote["timestamp"] == timestamp


def test_runtime_quote_authority_is_symbol_scoped() -> None:
    authority = _build_authority()

    timestamp = datetime(
        2026,
        9,
        7,
        14,
        30,
        tzinfo=timezone.utc,
    )

    authority.publish_quote(
        symbol="NQ",
        bid=25000.25,
        ask=25000.75,
        timestamp=timestamp,
    )

    assert authority.get_quote(
        symbol="ES"
    ) is None


def test_runtime_quote_authority_rejects_ask_below_bid() -> None:
    authority = _build_authority()

    timestamp = datetime(
        2026,
        9,
        7,
        14,
        30,
        tzinfo=timezone.utc,
    )

    with pytest.raises(ValueError):
        authority.publish_quote(
            symbol="NQ",
            bid=25000.75,
            ask=25000.25,
            timestamp=timestamp,
        )


def test_runtime_quote_authority_rejects_nonpositive_prices() -> None:
    authority = _build_authority()

    timestamp = datetime(
        2026,
        9,
        7,
        14,
        30,
        tzinfo=timezone.utc,
    )

    with pytest.raises(ValueError):
        authority.publish_quote(
            symbol="NQ",
            bid=0.0,
            ask=25000.75,
            timestamp=timestamp,
        )

    with pytest.raises(ValueError):
        authority.publish_quote(
            symbol="NQ",
            bid=25000.25,
            ask=0.0,
            timestamp=timestamp,
        )


def test_runtime_quote_authority_rejects_empty_symbol() -> None:
    authority = _build_authority()

    timestamp = datetime(
        2026,
        9,
        7,
        14,
        30,
        tzinfo=timezone.utc,
    )

    with pytest.raises(ValueError):
        authority.publish_quote(
            symbol=" ",
            bid=25000.25,
            ask=25000.75,
            timestamp=timestamp,
        )


def test_runtime_quote_authority_rejects_naive_timestamp() -> None:
    authority = _build_authority()

    timestamp = datetime(
        2026,
        9,
        7,
        14,
        30,
    )

    with pytest.raises(ValueError):
        authority.publish_quote(
            symbol="NQ",
            bid=25000.25,
            ask=25000.75,
            timestamp=timestamp,
        )


def test_runtime_quote_authority_normalizes_symbol() -> None:
    authority = _build_authority()

    timestamp = datetime(
        2026,
        9,
        7,
        14,
        30,
        tzinfo=timezone.utc,
    )

    authority.publish_quote(
        symbol=" nq ",
        bid=25000.25,
        ask=25000.75,
        timestamp=timestamp,
    )

    quote = authority.get_quote(
        symbol="NQ",
    )

    assert quote is not None
    assert quote["symbol"] == "NQ"


def test_runtime_quote_authority_replaces_quote_with_newer_quote() -> None:
    authority = _build_authority()

    older = datetime(
        2026,
        9,
        7,
        14,
        30,
        tzinfo=timezone.utc,
    )

    newer = datetime(
        2026,
        9,
        7,
        14,
        30,
        1,
        tzinfo=timezone.utc,
    )

    authority.publish_quote(
        symbol="NQ",
        bid=25000.25,
        ask=25000.75,
        timestamp=older,
    )

    authority.publish_quote(
        symbol="NQ",
        bid=25001.00,
        ask=25001.50,
        timestamp=newer,
    )

    quote = authority.get_quote(
        symbol="NQ",
    )

    assert quote is not None
    assert quote["bid"] == pytest.approx(
        25001.00
    )
    assert quote["ask"] == pytest.approx(
        25001.50
    )
    assert quote["timestamp"] == newer


def test_runtime_quote_authority_rejects_older_quote() -> None:
    authority = _build_authority()

    newer = datetime(
        2026,
        9,
        7,
        14,
        30,
        1,
        tzinfo=timezone.utc,
    )

    older = datetime(
        2026,
        9,
        7,
        14,
        30,
        tzinfo=timezone.utc,
    )

    authority.publish_quote(
        symbol="NQ",
        bid=25001.00,
        ask=25001.50,
        timestamp=newer,
    )

    with pytest.raises(ValueError):
        authority.publish_quote(
            symbol="NQ",
            bid=25000.25,
            ask=25000.75,
            timestamp=older,
        )


def test_runtime_quote_authority_exposes_real_bid_ask_not_last_price() -> None:
    authority = _build_authority()

    timestamp = datetime(
        2026,
        9,
        7,
        14,
        30,
        tzinfo=timezone.utc,
    )

    authority.publish_quote(
        symbol="NQ",
        bid=25000.25,
        ask=25000.75,
        timestamp=timestamp,
    )

    quote = authority.get_quote(
        symbol="NQ",
    )

    assert quote is not None
    assert "bid" in quote
    assert "ask" in quote

    assert quote["ask"] > quote["bid"]
