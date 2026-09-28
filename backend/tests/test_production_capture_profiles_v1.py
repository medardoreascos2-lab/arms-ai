"""Offline long-profile contract tests. No network, NinjaTrader or execution."""

import pytest

from tools.production_capture_contract_v1 import Budget, Coordinator
from tools.production_capture_profiles_v1 import PROFILES, profile


RUN = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
SESSION = "bbbbbbbb-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def long_engine(profile_id):
    p = profile(profile_id)
    return Coordinator(
        run_id=RUN,
        epoch=RUN,
        frequency=1,
        ready_qpc=0,
        budget=Budget(
            p.activation_timeout_seconds,
            p.minimum_duration_seconds,
            p.acknowledgement_seconds,
            p.closure_seconds,
            p.final_clock_seconds,
        ),
        profile_id=profile_id,
    )


def tick(c, qpc, **kwargs):
    return c.tick(
        qpc,
        epoch=RUN,
        frequency=1,
        **kwargs,
    )


def start(c, at=100):
    result = tick(c, at, session=SESSION)
    assert result["state"] == "CAPTURING"
    return at


def test_profiles_are_closed_and_expected():
    assert tuple(PROFILES) == ("LONG_A", "LONG_B", "LONG_C")

    a = profile("LONG_A")
    b = profile("LONG_B")
    c = profile("LONG_C")

    assert (a.minimum_duration_seconds, a.minimum_closed, a.hard_maximum_duration_seconds) == (
        3600, 50, 7200
    )
    assert (b.minimum_duration_seconds, b.minimum_closed, b.hard_maximum_duration_seconds) == (
        3600, 50, 7200
    )
    assert (c.minimum_duration_seconds, c.minimum_closed, c.hard_maximum_duration_seconds) == (
        21600, 300, 28800
    )

    assert a.profile_id != b.profile_id != c.profile_id

    with pytest.raises(ValueError, match="PROFILE_NOT_ALLOWLISTED"):
        profile("LONG_X")

    with pytest.raises(ValueError, match="PROFILE_NOT_ALLOWLISTED"):
        profile(123)


@pytest.mark.parametrize(
    "profile_id,min_seconds,min_closed,hard_max",
    [
        ("LONG_A", 3600, 50, 7200),
        ("LONG_B", 3600, 50, 7200),
        ("LONG_C", 21600, 300, 28800),
    ],
)
def test_long_profile_requires_both_duration_and_closed_count(
    profile_id, min_seconds, min_closed, hard_max
):
    # Scenario 1: count alone cannot complete before minimum duration.
    c = long_engine(profile_id)
    start_qpc = start(c)

    before = tick(
        c,
        start_qpc + min_seconds - 1,
        closed=min_closed,
    )
    assert before["state"] == "CAPTURING"
    assert before["reason"] is None

    # Scenario 2: minimum duration alone is insufficient without enough CLOSED.
    # Use a fresh coordinator so CLOSED is monotonic within the run.
    c = long_engine(profile_id)
    start_qpc = start(c)

    at_min = tick(
        c,
        start_qpc + min_seconds,
        closed=min_closed - 1,
    )
    assert at_min["state"] == "CAPTURING"
    assert at_min["reason"] is None

    # Scenario 3: insufficient history may continue until just before hard max.
    c = long_engine(profile_id)
    start_qpc = start(c)

    before_hard = tick(
        c,
        start_qpc + hard_max - 1,
        closed=min_closed - 1,
    )
    assert before_hard["state"] == "CAPTURING"
    assert before_hard["reason"] is None


@pytest.mark.parametrize(
    "profile_id,min_seconds,min_closed",
    [
        ("LONG_A", 3600, 50),
        ("LONG_B", 3600, 50),
        ("LONG_C", 21600, 300),
    ],
)
def test_long_profile_becomes_remove_eligible_only_when_both_are_satisfied(
    profile_id, min_seconds, min_closed
):
    c = long_engine(profile_id)
    start_qpc = start(c)

    result = tick(
        c,
        start_qpc + min_seconds,
        closed=min_closed,
    )

    assert result["state"] == "REMOVE_REQUESTED"
    assert result["reason"] is None
    assert c.request_id == RUN + ":remove:1"
    assert result["runtime_admission"] is False


@pytest.mark.parametrize(
    "profile_id,hard_max,min_closed",
    [
        ("LONG_A", 7200, 50),
        ("LONG_B", 7200, 50),
        ("LONG_C", 28800, 300),
    ],
)
def test_hard_max_with_insufficient_history_fails_closed(
    profile_id, hard_max, min_closed
):
    c = long_engine(profile_id)
    start_qpc = start(c)

    result = tick(
        c,
        start_qpc + hard_max,
        closed=min_closed - 1,
    )

    assert result["state"] == "FAILED"
    assert result["reason"] == "INCOMPLETE_HISTORY"
    assert result["runtime_admission"] is False
    assert result["collector_must_continue"] is False

    # Fault must latch.
    assert tick(c, start_qpc + hard_max + 1, closed=min_closed) == result


def test_profile_budget_mismatch_is_rejected():
    p = profile("LONG_A")

    with pytest.raises(ValueError, match="PROFILE_BUDGET"):
        Coordinator(
            run_id=RUN,
            epoch=RUN,
            frequency=1,
            ready_qpc=0,
            budget=Budget(
                p.activation_timeout_seconds,
                p.minimum_duration_seconds + 1,
                p.acknowledgement_seconds,
                p.closure_seconds,
                p.final_clock_seconds,
            ),
            profile_id="LONG_A",
        )


def test_short_capture_semantics_remain_profile_free():
    c = Coordinator(
        run_id=RUN,
        epoch=RUN,
        frequency=10,
        ready_qpc=0,
        budget=Budget(600, 330, 60, 30, 30),
    )

    assert c.profile is None

    tick_short = lambda q, **kw: c.tick(
        q,
        epoch=RUN,
        frequency=10,
        **kw,
    )

    assert tick_short(100, session=SESSION)["state"] == "CAPTURING"

    # 329.9 seconds: still capturing.
    assert tick_short(3399, closed=3)["state"] == "CAPTURING"

    # 330 seconds: existing short contract requests removal.
    result = tick_short(3400, closed=3)
    assert result["state"] == "REMOVE_REQUESTED"
    assert result["reason"] is None
    assert result["runtime_admission"] is False



@pytest.mark.parametrize(
    "profile_id,hard_max,min_closed",
    [
        ("LONG_A", 7200, 50),
        ("LONG_B", 7200, 50),
        ("LONG_C", 28800, 300),
    ],
)
def test_exact_hard_max_can_complete_when_closed_threshold_is_met(
    profile_id, hard_max, min_closed
):
    c = long_engine(profile_id)
    start_qpc = start(c)

    result = tick(
        c,
        start_qpc + hard_max,
        closed=min_closed,
    )

    assert result["state"] == "REMOVE_REQUESTED"
    assert result["reason"] is None
    assert result["runtime_admission"] is False


@pytest.mark.parametrize(
    "profile_id,hard_max,min_closed",
    [
        ("LONG_A", 7200, 50),
        ("LONG_B", 7200, 50),
        ("LONG_C", 28800, 300),
    ],
)
def test_hard_max_is_absolute_even_when_closed_threshold_is_met(
    profile_id, hard_max, min_closed
):
    c = long_engine(profile_id)
    start_qpc = start(c)

    result = tick(
        c,
        start_qpc + hard_max + 1,
        closed=min_closed,
    )

    assert result["state"] == "FAILED"
    assert result["reason"] == "CAPTURE_HARD_MAX_EXCEEDED"
    assert result["runtime_admission"] is False
    assert result["collector_must_continue"] is False

    # Fault remains latched.
    assert tick(
        c,
        start_qpc + hard_max + 2,
        closed=min_closed,
    ) == result



def test_long_sealed_protocol_survives_module_alias_identity():
    """CLI -m execution creates __main__.SealedCapture, not canonical class."""
    p = profile("LONG_A")

    c = Coordinator(
        run_id=RUN,
        epoch=RUN,
        frequency=1,
        ready_qpc=0,
        budget=Budget(
            p.activation_timeout_seconds,
            p.minimum_duration_seconds,
            p.acknowledgement_seconds,
            p.closure_seconds,
            p.final_clock_seconds,
        ),
        profile_id="LONG_A",
    )

    # Activate.
    assert tick(c, 1, session=SESSION)["state"] == "CAPTURING"

    # Reach minimum duration + CLOSED threshold.
    request_qpc = 1 + p.minimum_duration_seconds
    assert tick(
        c,
        request_qpc,
        closed=p.minimum_closed,
    )["state"] == "REMOVE_REQUESTED"

    proof = {
        "status": "PASS",
        "session": SESSION,
        "qpc_frequency": 1,
        "first_callback": {"qpc_before": 2},
        "last_emission": {"qpc_after": request_qpc},
        "closed": p.minimum_closed,
    }

    calls = []

    # Deliberately NOT production_capture_long_v1.SealedCapture.
    # This simulates the class identity produced by python -m / __main__.
    ForeignSealedCapture = type(
        "SealedCapture",
        (),
        {
            "__module__": "__main__",
            "profile_id": "LONG_A",
            "proof": proof,
            "signature": (("synthetic", (1, 1), 1, "0" * 64),),
            "quick_verify": lambda self: calls.append("verified"),
        },
    )

    sealed = ForeignSealedCapture()

    result = tick(
        c,
        request_qpc + 1,
        closed=p.minimum_closed,
        sealed=sealed,
        exclusive_closed=True,
    )

    assert result["state"] == "REMOVE_REQUESTED"
    assert result["reason"] is None
    assert result["pending_closure"] is True
    assert calls == ["verified"]


def test_long_sealed_protocol_rejects_unverified_foreign_object():
    p = profile("LONG_A")

    c = Coordinator(
        run_id=RUN,
        epoch=RUN,
        frequency=1,
        ready_qpc=0,
        budget=Budget(
            p.activation_timeout_seconds,
            p.minimum_duration_seconds,
            p.acknowledgement_seconds,
            p.closure_seconds,
            p.final_clock_seconds,
        ),
        profile_id="LONG_A",
    )

    tick(c, 1, session=SESSION)
    request_qpc = 1 + p.minimum_duration_seconds

    tick(
        c,
        request_qpc,
        closed=p.minimum_closed,
    )

    class Fake:
        profile_id = "LONG_A"
        proof = {}
        signature = ()

    result = tick(
        c,
        request_qpc + 1,
        closed=p.minimum_closed,
        sealed=Fake(),
        exclusive_closed=True,
    )

    assert result["state"] == "FAILED"
    assert result["reason"] == "INVALID_SEALED_STREAM"
