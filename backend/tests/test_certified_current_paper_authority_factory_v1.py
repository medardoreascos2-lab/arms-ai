"""Offline construction checks for the explicit, fresh Current PAPER owner."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

import backend.backtesting.certified_current_paper_authority_factory_v1 as factory
from backend.backtesting.current_paper_runtime_v1 import CurrentPaperServiceV1
from backend.tests.test_paper_research_sprint07r import config
from backend.tests.test_production_certified_outcome_v17 import api_settings


NOW = datetime(2026, 10, 1, 14, tzinfo=timezone.utc)
TEMPLATE = (
    b"<Root><TradingHours><Name>CME US Index Futures ETH</Name>"
    b"<TimeZone>Central Standard Time</TimeZone>"
    b"<HolidaysSerializable/><PartialHolidaysSerializable/>"
    b"</TradingHours></Root>"
)
LOADED = b"reviewed-native-snapshot\n"


def _inputs(tmp_path, monkeypatch, api_settings):
    monkeypatch.setattr(factory, "TEMPLATE_SHA256", sha256(TEMPLATE).hexdigest())
    monkeypatch.setattr(factory, "NATIVE_SHA256", sha256(LOADED).hexdigest())
    verified = []
    monkeypatch.setattr(
        factory, "verify_loaded_binding",
        lambda loaded, template: verified.append((loaded, template)),
    )
    begin = NOW - timedelta(days=1)
    end = NOW + timedelta(days=1)
    first = begin.astimezone(factory.CHICAGO).date() - timedelta(days=1)
    last = end.astimezone(factory.CHICAGO).date() + timedelta(days=1)
    days = []
    day = first
    while day <= last:
        days.append(day.isoformat())
        day += timedelta(days=1)
    spec = {
        "schema": "arms.native-capture-spec.sprint13.v1",
        "status": "ORDINARY_LOCAL_AND_LOADED_NATIVE_CALENDAR_BOUND",
        "unknown_policy": "FAIL_CLOSED", "order_authority": False,
        "provider_enum": "Provider31", "expiry": "2026-12-01",
        "calendar_evidence_file": "reviewed.xml",
        "calendar_evidence_sha256": factory.TEMPLATE_SHA256,
        "loaded_calendar_evidence_file": "reviewed.calendar.jsonl",
        "loaded_calendar_evidence_sha256": factory.NATIVE_SHA256,
        "covered_dates": days, "closed_dates": [], "special_hours": [],
        "contract": {
            "provider": "Provider31", "contract": "NQ DEC26",
            "instrument": "NQ", "source_timezone": "UTC",
            "bar_label": "CLOSE",
            "trading_hours_template": "CME US Index Futures ETH",
            "tick_size": .25, "point_value": 20, "fixture": False,
            "valid_from": begin.isoformat(), "valid_until": end.isoformat(),
        },
    }
    args = dict(
        template_bytes=TEMPLATE, loaded_calendar_bytes=LOADED,
        config=config(), settings=api_settings,
        state_path=tmp_path / "paper.sqlite", clock=lambda: NOW,
    )
    return spec, args, verified


def _create(spec, args):
    raw = json.dumps(spec, sort_keys=True).encode()
    return factory.create_certified_current_paper_service_v1(
        spec_bytes=raw, reviewed_spec_sha256=sha256(raw).hexdigest(), **args,
    )


def test_exact_fresh_service_and_paper_disabled(tmp_path, monkeypatch, api_settings):
    spec, args, verified = _inputs(tmp_path, monkeypatch, api_settings)
    original = json.dumps(spec, sort_keys=True)
    service = _create(spec, args)
    assert type(service) is CurrentPaperServiceV1
    assert service._runtime is None
    assert service._strategy_bootstrap is None
    assert service._stopped is False
    assert service._arguments["initialization_policy"] == "NEW_ISOLATED_PAPER_ACCOUNT"
    assert service.gate.maximum_age == api_settings.maximum_quote_age_seconds
    assert service.gate.connected is False
    assert service.gate.fault is None
    assert service.gate.last_sequence is None
    assert service.gate.closed_count == 0
    assert "PAPER_DISABLED" in service.get_snapshot()["readiness_reasons"]
    assert service.gate.contract.provider == "NINJATRADER:Provider31"
    assert verified == [(LOADED, TEMPLATE)]
    assert json.dumps(spec, sort_keys=True) == original
    assert not args["state_path"].exists()


@pytest.mark.parametrize("change", (
    "bad_hash", "fixture", "provider", "coverage", "unknown_policy",
    "order_authority", "stale_window", "existing_state",
))
def test_unreviewed_or_unsafe_inputs_fail_closed(
    tmp_path, monkeypatch, api_settings, change,
):
    spec, args, _ = _inputs(tmp_path, monkeypatch, api_settings)
    if change == "fixture":
        spec["contract"]["fixture"] = True
    elif change == "provider":
        spec["provider_enum"] = "OTHER"
    elif change == "coverage":
        spec["covered_dates"].pop()
    elif change == "unknown_policy":
        spec["unknown_policy"] = "ASSUME_OPEN"
    elif change == "order_authority":
        spec["order_authority"] = True
    elif change == "stale_window":
        spec["contract"]["valid_until"] = (NOW - timedelta(seconds=1)).isoformat()
    elif change == "existing_state":
        args["state_path"].write_bytes(b"existing-state")
    raw = json.dumps(spec, sort_keys=True).encode()
    digest = sha256(raw).hexdigest()
    if change == "bad_hash":
        digest = "0" * 64
    with pytest.raises((ValueError, TypeError)):
        factory.create_certified_current_paper_service_v1(
            spec_bytes=raw, reviewed_spec_sha256=digest, **args,
        )


def test_exception_date_cannot_be_certified_as_ordinary(
    tmp_path, monkeypatch, api_settings,
):
    spec, args, _ = _inputs(tmp_path, monkeypatch, api_settings)
    template = TEMPLATE.replace(
        b"<HolidaysSerializable/>",
        b"<HolidaysSerializable><Holiday><Date>2026-10-01</Date>"
        b"</Holiday></HolidaysSerializable>",
    )
    monkeypatch.setattr(factory, "TEMPLATE_SHA256", sha256(template).hexdigest())
    spec["calendar_evidence_sha256"] = factory.TEMPLATE_SHA256
    args["template_bytes"] = template
    with pytest.raises(ValueError, match="NATIVE_EXCEPTION_MAPPING_REQUIRED"):
        _create(spec, args)


def test_factory_has_no_legacy_or_native_reader_import():
    source = Path(factory.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "operational_paper_soak_v1", "operational_paper_v1",
        "ninjatrader_market_reader_v1", "CreateOrder(", "SubmitOrder",
    ):
        assert forbidden not in source
