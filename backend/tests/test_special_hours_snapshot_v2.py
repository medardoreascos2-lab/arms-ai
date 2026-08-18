from datetime import date
from datetime import datetime
from datetime import time
from zoneinfo import ZoneInfo

import pytest

from backend.services.special_hours_snapshot_v2 import (
    CertifiedSpecialHoursSnapshotV2,
    CertifiedSpecialHoursWindowV2,
    SpecialHoursResolverV2,
)


CHICAGO = ZoneInfo("America/Chicago")
NEW_YORK = ZoneInfo("America/New_York")


def build_window() -> CertifiedSpecialHoursWindowV2:
    return CertifiedSpecialHoursWindowV2(
        local_date=date(2026, 11, 27),
        open_time=time(8, 30),
        close_time=time(12, 15),
    )


def build_resolver() -> SpecialHoursResolverV2:
    return SpecialHoursResolverV2(
        snapshot=CertifiedSpecialHoursSnapshotV2(
            windows=(build_window(),)
        )
    )


def test_window_is_immutable():
    window = build_window()

    with pytest.raises(
        AttributeError,
    ):
        window.close_time = time(13, 0)


def test_snapshot_is_immutable():
    snapshot = CertifiedSpecialHoursSnapshotV2(
        windows=(build_window(),)
    )

    with pytest.raises(
        AttributeError,
    ):
        snapshot.windows = ()


def test_snapshot_requires_tuple():
    with pytest.raises(
        TypeError,
        match="windows",
    ):
        CertifiedSpecialHoursSnapshotV2(
            windows=[build_window()]
        )


def test_snapshot_rejects_invalid_window():
    with pytest.raises(
        TypeError,
        match="windows",
    ):
        CertifiedSpecialHoursSnapshotV2(
            windows=("invalid",)
        )


def test_snapshot_rejects_duplicate_date():
    first = build_window()
    second = CertifiedSpecialHoursWindowV2(
        local_date=first.local_date,
        open_time=time(9, 0),
        close_time=time(11, 0),
    )

    with pytest.raises(
        ValueError,
        match="más de una ventana",
    ):
        CertifiedSpecialHoursSnapshotV2(
            windows=(first, second)
        )


def test_window_rejects_invalid_date():
    with pytest.raises(
        TypeError,
        match="local_date",
    ):
        CertifiedSpecialHoursWindowV2(
            local_date="2026-11-27",
            open_time=time(8, 30),
            close_time=time(12, 15),
        )


def test_window_rejects_invalid_open_time():
    with pytest.raises(
        TypeError,
        match="open_time",
    ):
        CertifiedSpecialHoursWindowV2(
            local_date=date(2026, 11, 27),
            open_time="08:30",
            close_time=time(12, 15),
        )


def test_window_rejects_invalid_close_time():
    with pytest.raises(
        TypeError,
        match="close_time",
    ):
        CertifiedSpecialHoursWindowV2(
            local_date=date(2026, 11, 27),
            open_time=time(8, 30),
            close_time="12:15",
        )


def test_window_rejects_equal_times():
    with pytest.raises(
        ValueError,
        match="menor",
    ):
        CertifiedSpecialHoursWindowV2(
            local_date=date(2026, 11, 27),
            open_time=time(12, 15),
            close_time=time(12, 15),
        )


def test_window_rejects_reverse_times():
    with pytest.raises(
        ValueError,
        match="menor",
    ):
        CertifiedSpecialHoursWindowV2(
            local_date=date(2026, 11, 27),
            open_time=time(13, 0),
            close_time=time(12, 15),
        )


def test_no_snapshot_returns_none():
    resolver = SpecialHoursResolverV2()

    assert resolver.resolve(
        symbol="NQ",
        timestamp=datetime(
            2026,
            11,
            27,
            10,
            0,
            tzinfo=CHICAGO,
        ),
    ) is None


def test_uncovered_date_returns_none():
    resolver = build_resolver()

    assert resolver.resolve(
        symbol="NQ",
        timestamp=datetime(
            2026,
            11,
            28,
            10,
            0,
            tzinfo=CHICAGO,
        ),
    ) is None


def test_inside_window_returns_true():
    resolver = build_resolver()

    assert resolver.resolve(
        symbol="NQ",
        timestamp=datetime(
            2026,
            11,
            27,
            10,
            0,
            tzinfo=CHICAGO,
        ),
    ) is True


def test_open_boundary_is_inclusive():
    resolver = build_resolver()

    assert resolver.resolve(
        symbol="NQ",
        timestamp=datetime(
            2026,
            11,
            27,
            8,
            30,
            tzinfo=CHICAGO,
        ),
    ) is True


def test_close_boundary_is_exclusive():
    resolver = build_resolver()

    assert resolver.resolve(
        symbol="NQ",
        timestamp=datetime(
            2026,
            11,
            27,
            12,
            15,
            tzinfo=CHICAGO,
        ),
    ) is False


def test_before_window_returns_false():
    resolver = build_resolver()

    assert resolver.resolve(
        symbol="NQ",
        timestamp=datetime(
            2026,
            11,
            27,
            8,
            29,
            tzinfo=CHICAGO,
        ),
    ) is False


def test_after_window_returns_false():
    resolver = build_resolver()

    assert resolver.resolve(
        symbol="NQ",
        timestamp=datetime(
            2026,
            11,
            27,
            13,
            0,
            tzinfo=CHICAGO,
        ),
    ) is False


def test_supports_mnq():
    resolver = build_resolver()

    assert resolver.resolve(
        symbol="MNQ",
        timestamp=datetime(
            2026,
            11,
            27,
            10,
            0,
            tzinfo=CHICAGO,
        ),
    ) is True


def test_normalizes_symbol():
    resolver = build_resolver()

    assert resolver.resolve(
        symbol=" nq ",
        timestamp=datetime(
            2026,
            11,
            27,
            10,
            0,
            tzinfo=CHICAGO,
        ),
    ) is True


def test_unknown_symbol_returns_none():
    resolver = build_resolver()

    assert resolver.resolve(
        symbol="ES",
        timestamp=datetime(
            2026,
            11,
            27,
            10,
            0,
            tzinfo=CHICAGO,
        ),
    ) is None


def test_timezone_conversion_new_york():
    resolver = build_resolver()

    assert resolver.resolve(
        symbol="NQ",
        timestamp=datetime(
            2026,
            11,
            27,
            11,
            0,
            tzinfo=NEW_YORK,
        ),
    ) is True


def test_rejects_naive_timestamp():
    resolver = build_resolver()

    with pytest.raises(
        ValueError,
        match="timezone",
    ):
        resolver.resolve(
            symbol="NQ",
            timestamp=datetime(
                2026,
                11,
                27,
                10,
                0,
            ),
        )


def test_rejects_invalid_timestamp():
    resolver = build_resolver()

    with pytest.raises(
        TypeError,
        match="timestamp",
    ):
        resolver.resolve(
            symbol="NQ",
            timestamp="invalid",
        )


def test_rejects_empty_symbol():
    resolver = build_resolver()

    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        resolver.resolve(
            symbol=" ",
            timestamp=datetime(
                2026,
                11,
                27,
                10,
                0,
                tzinfo=CHICAGO,
            ),
        )


def test_rejects_invalid_snapshot():
    with pytest.raises(
        TypeError,
        match="snapshot",
    ):
        SpecialHoursResolverV2(
            snapshot=object()
        )


def test_build_context_inside_window():
    resolver = build_resolver()

    context = resolver.build_special_hours_context(
        symbol="NQ",
        timestamp=datetime(
            2026,
            11,
            27,
            10,
            0,
            tzinfo=CHICAGO,
        ),
    )

    assert context["special_hours_certified"] is True
    assert context["special_hours_status"] is True
    assert context["special_hours_open"] is True
    assert context["special_open_time"] == "08:30:00"
    assert context["special_close_time"] == "12:15:00"


def test_build_context_outside_window():
    resolver = build_resolver()

    context = resolver.build_special_hours_context(
        symbol="NQ",
        timestamp=datetime(
            2026,
            11,
            27,
            13,
            0,
            tzinfo=CHICAGO,
        ),
    )

    assert context["special_hours_certified"] is True
    assert context["special_hours_status"] is False
    assert context["special_hours_open"] is False


def test_build_context_unknown_date():
    resolver = build_resolver()

    context = resolver.build_special_hours_context(
        symbol="NQ",
        timestamp=datetime(
            2026,
            11,
            28,
            10,
            0,
            tzinfo=CHICAGO,
        ),
    )

    assert context["special_hours_certified"] is False
    assert context["special_hours_status"] is None
    assert context["special_hours_open"] is False
    assert context["special_open_time"] is None
    assert context["special_close_time"] is None
