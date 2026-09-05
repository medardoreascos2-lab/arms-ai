from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from pathlib import Path

import pytest


LIVE_SERVICE_PATH = Path(
    "backend/services/live_market_analysis_service.py"
)


def _canonical_signal_age_seconds(
    *,
    signal_timestamp: datetime,
    now: datetime,
) -> int:
    """
    Target V81 freshness contract.

    UTC-aware timestamps are compared directly.

    Naive timestamps are interpreted as UTC for compatibility
    with existing Candle producers in the repository.

    Future timestamps are rejected rather than silently converted
    into a valid age.
    """
    if not isinstance(signal_timestamp, datetime):
        raise TypeError(
            "signal_timestamp debe ser datetime."
        )

    if not isinstance(now, datetime):
        raise TypeError(
            "now debe ser datetime."
        )

    normalized_signal_timestamp = signal_timestamp
    normalized_now = now

    if normalized_signal_timestamp.tzinfo is None:
        normalized_signal_timestamp = (
            normalized_signal_timestamp.replace(
                tzinfo=timezone.utc,
            )
        )
    else:
        normalized_signal_timestamp = (
            normalized_signal_timestamp.astimezone(
                timezone.utc,
            )
        )

    if normalized_now.tzinfo is None:
        normalized_now = normalized_now.replace(
            tzinfo=timezone.utc,
        )
    else:
        normalized_now = normalized_now.astimezone(
            timezone.utc,
        )

    age_seconds = (
        normalized_now
        - normalized_signal_timestamp
    ).total_seconds()

    if age_seconds < 0:
        raise ValueError(
            "signal_timestamp no puede estar "
            "en el futuro."
        )

    return int(age_seconds)


def test_target_contract_fresh_signal_age():
    now = datetime(
        2026,
        9,
        5,
        3,
        0,
        30,
        tzinfo=timezone.utc,
    )

    timestamp = now - timedelta(
        seconds=5,
    )

    assert (
        _canonical_signal_age_seconds(
            signal_timestamp=timestamp,
            now=now,
        )
        == 5
    )


def test_target_contract_stale_signal_age():
    now = datetime(
        2026,
        9,
        5,
        3,
        1,
        0,
        tzinfo=timezone.utc,
    )

    timestamp = now - timedelta(
        seconds=31,
    )

    assert (
        _canonical_signal_age_seconds(
            signal_timestamp=timestamp,
            now=now,
        )
        == 31
    )


def test_target_contract_naive_timestamp_is_utc_compatible():
    now = datetime(
        2026,
        9,
        5,
        3,
        0,
        30,
        tzinfo=timezone.utc,
    )

    timestamp = datetime(
        2026,
        9,
        5,
        3,
        0,
        20,
    )

    assert (
        _canonical_signal_age_seconds(
            signal_timestamp=timestamp,
            now=now,
        )
        == 10
    )


def test_target_contract_future_timestamp_is_rejected():
    now = datetime(
        2026,
        9,
        5,
        3,
        0,
        30,
        tzinfo=timezone.utc,
    )

    timestamp = now + timedelta(
        seconds=1,
    )

    with pytest.raises(
        ValueError,
        match="futuro",
    ):
        _canonical_signal_age_seconds(
            signal_timestamp=timestamp,
            now=now,
        )


def test_live_service_must_not_use_hardcoded_signal_age():
    source = LIVE_SERVICE_PATH.read_text(
        encoding="utf-8",
    )

    assert (
        "signal_age_seconds=5"
        not in source
    ), (
        "V81 GAP #1 todavía existe: "
        "LiveMarketAnalysisService usa "
        "signal_age_seconds=5 hardcodeado."
    )


def test_live_service_must_derive_age_from_analysis_timestamp():
    source = LIVE_SERVICE_PATH.read_text(
        encoding="utf-8",
    )

    assert (
        'result["analyzed_at"]'
        in source
    )

    assert (
        "signal_age_seconds="
        in source
    )

    validator_window_start = source.find(
        "self.trade_validator_v2.validate("
    )

    assert validator_window_start >= 0

    validator_window = source[
        validator_window_start:
        validator_window_start + 1200
    ]

    assert (
        "signal_age_seconds=5"
        not in validator_window
    )
