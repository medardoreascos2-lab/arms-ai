from backend.risk.signal_controller_v2 import (
    SignalControllerV2,
)


def test_first_signal_is_allowed():

    controller = SignalControllerV2(
        cooldown_bars=10
    )

    result = controller.evaluate(
        current_index=100,
        direction="LONG",
        grade="A",
    )

    assert result.allowed is True
    assert result.reason == "FIRST SIGNAL"


def test_same_direction_inside_cooldown_is_blocked():

    controller = SignalControllerV2(
        cooldown_bars=10
    )

    controller.register_trade(
        index=100,
        direction="LONG",
    )

    result = controller.evaluate(
        current_index=105,
        direction="LONG",
        grade="A+",
    )

    assert result.allowed is False

    assert (
        result.reason
        == "SAME DIRECTION COOLDOWN"
    )


def test_direction_change_is_allowed():

    controller = SignalControllerV2(
        cooldown_bars=10
    )

    controller.register_trade(
        index=100,
        direction="LONG",
    )

    result = controller.evaluate(
        current_index=105,
        direction="SHORT",
        grade="A",
    )

    assert result.allowed is True
    assert result.reason == "DIRECTION CHANGE"


def test_a_plus_after_cooldown_is_allowed():

    controller = SignalControllerV2(
        cooldown_bars=10
    )

    controller.register_trade(
        index=100,
        direction="LONG",
    )

    result = controller.evaluate(
        current_index=115,
        direction="LONG",
        grade="A+",
    )

    assert result.allowed is True
    assert result.reason == "NEW A+ SETUP"


def test_non_a_plus_after_cooldown_waits():

    controller = SignalControllerV2(
        cooldown_bars=10
    )

    controller.register_trade(
        index=100,
        direction="LONG",
    )

    result = controller.evaluate(
        current_index=115,
        direction="LONG",
        grade="A",
    )

    assert result.allowed is False
    assert result.reason == "WAITING"
