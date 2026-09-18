"""Explicit certified market fixtures for operational PAPER integration tests.

Never installed globally: the original V8 missing-data tests remain empty.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

NOW = datetime(2026, 9, 8, 15, tzinfo=timezone.utc)


def publish_test_market(lifecycle, *, directory, symbol="MNQ", price=10000.,
                        quote_age=0, closed=False, news_blocked=False, spread=.25):
    admission = lifecycle.runtime_admission_v2
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    hours = directory / "test-certified-hours.json"
    hours.write_text(json.dumps({"covered_dates": [NOW.date().isoformat()],
        "closed_dates": [NOW.date().isoformat()] if closed else [], "special_hours": []}), encoding="utf-8")
    news = directory / "test-certified-news.json"
    news.write_text(json.dumps({"snapshot_version": "explicit-test-v81",
        "generated_at": (NOW-timedelta(hours=1)).isoformat(),
        "coverage_start": (NOW-timedelta(hours=1)).isoformat(),
        "coverage_end": (NOW+timedelta(hours=1)).isoformat(),
        "high_impact_events": [NOW.isoformat()] if news_blocked else []}), encoding="utf-8")
    admission.clock = lambda: NOW
    admission.market_hours_lifecycle.activate_from_file(file_path=hours)
    admission.news_lifecycle.activate_from_file(file_path=news)
    admission.quote_authority.publish_quote(symbol=symbol, bid=price-spread/2,
        ask=price+spread/2, timestamp=NOW-timedelta(seconds=quote_age))
    return admission


def submit_with_test_market(lifecycle, **kwargs):
    """Supply explicit valid market fixtures, then traverse production admission."""
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(prefix="arms-test-market-") as directory:
        publish_test_market(lifecycle, directory=directory,
            symbol=kwargs["signal"]["symbol"], price=kwargs["signal"]["entry_price"])
        return lifecycle.submit_signal(**kwargs)


def isolated_policy_candidate(manager, **kwargs):
    """Exercise contract policy on an isolated preparer, never a runtime order."""
    from backend.execution.execution_manager_v2 import ExecutionManagerV2
    if getattr(manager, "_durability", None) is not None:
        import pytest
        from backend.services.durable_execution_state_v2 import AccountAdmissionRejected
        with pytest.raises(AccountAdmissionRejected, match="canonical_runtime_admission_required"):
            manager.prepare_order(**kwargs)
    isolated = ExecutionManagerV2(execution_mode=manager.execution_mode,
        maximum_contracts=manager.maximum_contracts,
        contract_limit_resolver=manager.contract_limit_resolver)
    return isolated.prepare_order(**kwargs)
