from __future__ import annotations

import threading

from backend.api.app import create_app


def build_lifecycle():
    app = create_app()
    return app.state.trade_lifecycle_service_v2


def signal(submission_id: str):
    return {
        "submission_id": submission_id,
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "grade": "A+",
        "probability": 0.95,
        "confluence_score": 0.95,
        "blocking_reasons": [],
        "warnings": [],
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 20000.0,
        "stop_loss": 19950.0,
        "take_profit": 20100.0,
        "contracts": 1,
    }


def test_explicit_submission_id_is_reserved_once():
    lifecycle = build_lifecycle()

    payload = signal("GATE5-SEQUENTIAL-001")

    assert lifecycle._reserve_submission(
        signal=payload,
        order_type="MARKET",
    )

    assert not lifecycle._reserve_submission(
        signal=dict(payload),
        order_type="MARKET",
    )


def test_same_trade_with_new_submission_id_is_allowed():
    lifecycle = build_lifecycle()

    first = signal("GATE5-TRADE-A")
    second = signal("GATE5-TRADE-B")

    assert lifecycle._reserve_submission(
        signal=first,
        order_type="MARKET",
    )

    assert lifecycle._reserve_submission(
        signal=second,
        order_type="MARKET",
    )


def test_concurrent_duplicate_has_one_winner():
    lifecycle = build_lifecycle()

    payload = signal("GATE5-CONCURRENT-001")

    barrier = threading.Barrier(8)
    results = []
    result_lock = threading.Lock()

    def worker():
        barrier.wait()

        accepted = lifecycle._reserve_submission(
            signal=dict(payload),
            order_type="MARKET",
        )

        with result_lock:
            results.append(accepted)

    threads = [
        threading.Thread(target=worker)
        for _ in range(8)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert results.count(True) == 1
    assert results.count(False) == 7


def test_legacy_retry_fingerprint_is_backward_compatible():
    lifecycle = build_lifecycle()

    payload = signal("TEMP")
    payload.pop("submission_id")

    assert lifecycle._reserve_submission(
        signal=payload,
        order_type="MARKET",
    )

    assert not lifecycle._reserve_submission(
        signal=dict(payload),
        order_type="MARKET",
    )
