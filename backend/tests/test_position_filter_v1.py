from backend.intelligence.position_filter_v1 import (
    PositionFilterV1,
)


def test_flat_allows_new_position():

    result = PositionFilterV1().evaluate(
        current_position="FLAT",
        new_direction="LONG",
    )

    assert result.allowed is True
    assert result.reason == "NO ACTIVE POSITION"


def test_existing_long_blocks_second_long():

    result = PositionFilterV1().evaluate(
        current_position="LONG",
        new_direction="LONG",
    )

    assert result.allowed is False
    assert result.reason == "ALREADY LONG"


def test_existing_short_blocks_second_short():

    result = PositionFilterV1().evaluate(
        current_position="SHORT",
        new_direction="SHORT",
    )

    assert result.allowed is False
    assert result.reason == "ALREADY SHORT"


def test_long_to_short_requires_close_first():

    result = PositionFilterV1().evaluate(
        current_position="LONG",
        new_direction="SHORT",
    )

    assert result.allowed is False

    assert (
        result.reason
        == "CLOSE EXISTING POSITION FIRST"
    )


def test_short_to_long_requires_close_first():

    result = PositionFilterV1().evaluate(
        current_position="SHORT",
        new_direction="LONG",
    )

    assert result.allowed is False

    assert (
        result.reason
        == "CLOSE EXISTING POSITION FIRST"
    )
