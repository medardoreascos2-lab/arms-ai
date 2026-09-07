from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.services.runtime_quote_authority_v2 import (
    RuntimeQuoteAuthorityV2,
)
from backend.services.spread_authority_v2 import (
    SpreadAuthorityV2,
)


def _runtime_spread_authority_class():
    from backend.services.runtime_spread_authority_v2 import (
        RuntimeSpreadAuthorityV2,
    )

    return RuntimeSpreadAuthorityV2


def _now() -> datetime:
    return datetime(
        2026,
        9,
        7,
        12,
        0,
        0,
        tzinfo=timezone.utc,
    )


def _build_authority(
    *,
    maximum_quote_age_seconds: float = 5.0,
):
    runtime_spread_authority = (
        _runtime_spread_authority_class()
    )

    quote_authority = RuntimeQuoteAuthorityV2()
    spread_authority = SpreadAuthorityV2()

    authority = runtime_spread_authority(
        quote_authority=quote_authority,
        spread_authority=spread_authority,
        maximum_quote_age_seconds=(
            maximum_quote_age_seconds
        ),
    )

    return (
        authority,
        quote_authority,
    )


def test_runtime_spread_uses_l1_bid_ask_quote() -> None:
    authority, quotes = _build_authority()

    now = _now()

    quotes.publish_quote(
        symbol="NQ",
        bid=20000.25,
        ask=20000.75,
        timestamp=now,
    )

    spread = authority.get_spread_points(
        symbol="NQ",
        now=now,
    )

    assert spread == pytest.approx(0.50)


def test_runtime_spread_changes_with_runtime_quote() -> None:
    authority, quotes = _build_authority()

    now = _now()

    quotes.publish_quote(
        symbol="NQ",
        bid=20000.00,
        ask=20000.25,
        timestamp=now,
    )

    first = authority.get_spread_points(
        symbol="NQ",
        now=now,
    )

    quotes.publish_quote(
        symbol="NQ",
        bid=20000.00,
        ask=20001.00,
        timestamp=now + timedelta(seconds=1),
    )

    second = authority.get_spread_points(
        symbol="NQ",
        now=now + timedelta(seconds=1),
    )

    assert first == pytest.approx(0.25)
    assert second == pytest.approx(1.00)
    assert second != first


def test_runtime_spread_is_symbol_scoped() -> None:
    authority, quotes = _build_authority()

    now = _now()

    quotes.publish_quote(
        symbol="NQ",
        bid=20000.00,
        ask=20000.50,
        timestamp=now,
    )

    quotes.publish_quote(
        symbol="ES",
        bid=6000.00,
        ask=6000.25,
        timestamp=now,
    )

    nq = authority.get_spread_points(
        symbol="NQ",
        now=now,
    )
    es = authority.get_spread_points(
        symbol="ES",
        now=now,
    )

    assert nq == pytest.approx(0.50)
    assert es == pytest.approx(0.25)


def test_missing_quote_fails_closed() -> None:
    authority, _ = _build_authority()

    with pytest.raises(
        RuntimeError,
        match="quote",
    ):
        authority.get_spread_points(
            symbol="NQ",
            now=_now(),
        )


def test_stale_quote_fails_closed() -> None:
    authority, quotes = _build_authority(
        maximum_quote_age_seconds=5.0,
    )

    now = _now()

    quotes.publish_quote(
        symbol="NQ",
        bid=20000.00,
        ask=20000.25,
        timestamp=now,
    )

    with pytest.raises(
        RuntimeError,
        match="stale",
    ):
        authority.get_spread_points(
            symbol="NQ",
            now=now + timedelta(seconds=6),
        )


def test_quote_at_freshness_boundary_is_allowed() -> None:
    authority, quotes = _build_authority(
        maximum_quote_age_seconds=5.0,
    )

    now = _now()

    quotes.publish_quote(
        symbol="NQ",
        bid=20000.00,
        ask=20000.50,
        timestamp=now,
    )

    spread = authority.get_spread_points(
        symbol="NQ",
        now=now + timedelta(seconds=5),
    )

    assert spread == pytest.approx(0.50)


def test_future_quote_fails_closed() -> None:
    authority, quotes = _build_authority()

    now = _now()

    quotes.publish_quote(
        symbol="NQ",
        bid=20000.00,
        ask=20000.25,
        timestamp=now + timedelta(seconds=1),
    )

    with pytest.raises(
        RuntimeError,
        match="future",
    ):
        authority.get_spread_points(
            symbol="NQ",
            now=now,
        )


def test_now_must_be_timezone_aware() -> None:
    authority, quotes = _build_authority()

    now = _now()

    quotes.publish_quote(
        symbol="NQ",
        bid=20000.00,
        ask=20000.25,
        timestamp=now,
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        authority.get_spread_points(
            symbol="NQ",
            now=datetime(
                2026,
                9,
                7,
                12,
                0,
                0,
            ),
        )


def test_maximum_quote_age_must_be_positive() -> None:
    runtime_spread_authority = (
        _runtime_spread_authority_class()
    )

    with pytest.raises(ValueError):
        runtime_spread_authority(
            quote_authority=RuntimeQuoteAuthorityV2(),
            spread_authority=SpreadAuthorityV2(),
            maximum_quote_age_seconds=0.0,
        )


def test_runtime_spread_has_no_static_fallback_contract() -> None:
    authority, _ = _build_authority()

    with pytest.raises(RuntimeError):
        authority.get_spread_points(
            symbol="NQ",
            now=_now(),
        )
