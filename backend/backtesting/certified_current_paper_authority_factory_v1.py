"""Pure, explicitly reviewed native authority construction for LOCAL PAPER.

The caller supplies pinned specification and calendar bytes. This module does
not discover a feed, open a native account, or grant PAPER control authority.
"""

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from secrets import compare_digest
import xml.etree.ElementTree as ET

from backend.backtesting.current_paper_runtime_v1 import CurrentPaperServiceV1
from backend.backtesting.current_paper_entry_authority_v1 import (
    CurrentPaperEntryAuthorityV1, current_paper_l1_reader,
)
from backend.services.current_paper_economic_news_authority_v1 import (
    CurrentPaperEconomicNewsAuthorityV1, runtime_binding,
)
from backend.backtesting.paper_research_v1 import PaperResearchConfigV1
from backend.config.api_settings import APISettings
from backend.market_data.current_candle_authority_v1 import (
    CHICAGO,
    CurrentCandleAuthorityV1,
    CurrentFeedContractV1,
)
from backend.market_data.loaded_calendar_binding_v1 import (
    NATIVE_SHA256,
    verify_loaded_binding,
)
from backend.market_data.native_calendar_review_v1 import TEMPLATE, TEMPLATE_SHA256
from backend.services.certified_market_calendar_v2 import CertifiedCalendarSnapshotV2
from backend.services.certified_market_hours_runtime_provider_v2 import (
    CertifiedMarketHoursRuntimeProviderV2,
)
from backend.services.special_hours_snapshot_v2 import CertifiedSpecialHoursSnapshotV2


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_REVIEWED_SPEC_KEY")
        result[key] = value
    return result


def _utc(value):
    if type(value) is not str:
        raise ValueError("REVIEWED_UTC_WINDOW_REQUIRED")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("REVIEWED_UTC_WINDOW_REQUIRED")
    return parsed.astimezone(timezone.utc)


def create_certified_current_paper_service_v1(
    *, spec_bytes, reviewed_spec_sha256, template_bytes,
    loaded_calendar_bytes, config, settings, state_path, clock,
    news_root=None, l1_directory=None, l1_directory_identity=None,
):
    """Build one fresh service from hash-pinned, ordinary native inputs.

    The out-of-band specification digest is the caller's explicit review pin.
    Native calendar evidence is a pinned snapshot, not continuous attestation.
    Unsupported exception dates and missing coverage remain fail-closed.
    """
    if (
        type(spec_bytes) is not bytes
        or not 0 < len(spec_bytes) <= 65536
        or type(reviewed_spec_sha256) is not str
        or len(reviewed_spec_sha256) != 64
        or any(c not in "0123456789abcdef" for c in reviewed_spec_sha256)
        or not compare_digest(sha256(spec_bytes).hexdigest(), reviewed_spec_sha256)
    ):
        raise ValueError("REVIEWED_NATIVE_SPEC_SHA256_REQUIRED")
    if type(template_bytes) is not bytes or type(loaded_calendar_bytes) is not bytes:
        raise TypeError("EXPLICIT_CALENDAR_EVIDENCE_REQUIRED")
    if type(config) is not PaperResearchConfigV1 or type(settings) is not APISettings:
        raise TypeError("CERTIFIED_PAPER_CONFIG_AND_RISK_SETTINGS_REQUIRED")
    if not callable(clock):
        raise TypeError("EXPLICIT_UTC_CLOCK_REQUIRED")
    now = clock()
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("EXPLICIT_UTC_CLOCK_REQUIRED")
    path = Path(state_path)
    if path.exists():
        raise ValueError("FRESH_PAPER_STATE_PATH_REQUIRED")

    spec = json.loads(spec_bytes, object_pairs_hook=_unique)
    if type(spec) is not dict:
        raise ValueError("REVIEWED_NATIVE_SPEC_REQUIRED")
    if (
        spec.get("schema") != "arms.native-capture-spec.sprint13.v1"
        or spec.get("status") != "ORDINARY_LOCAL_AND_LOADED_NATIVE_CALENDAR_BOUND"
        or spec.get("unknown_policy") != "FAIL_CLOSED"
        or spec.get("order_authority") is not False
        or spec.get("provider_enum") != "Provider31"
        or spec.get("expiry") != "2026-12-01"
        or spec.get("calendar_evidence_sha256") != TEMPLATE_SHA256
        or spec.get("loaded_calendar_evidence_sha256") != NATIVE_SHA256
        or not isinstance(spec.get("calendar_evidence_file"), str)
        or not spec["calendar_evidence_file"].strip()
        or not isinstance(spec.get("loaded_calendar_evidence_file"), str)
        or not spec["loaded_calendar_evidence_file"].strip()
        or sha256(template_bytes).hexdigest() != TEMPLATE_SHA256
        or sha256(loaded_calendar_bytes).hexdigest() != NATIVE_SHA256
    ):
        raise ValueError("REVIEWED_NATIVE_CALENDAR_IDENTITY_REQUIRED")
    template = ET.fromstring(template_bytes).find("TradingHours")
    if (
        template is None
        or template.findtext("Name") != TEMPLATE
        or template.findtext("TimeZone") != "Central Standard Time"
    ):
        raise ValueError("REVIEWED_NATIVE_CALENDAR_METADATA_REQUIRED")
    verify_loaded_binding(loaded_calendar_bytes, template_bytes)

    data = spec.get("contract")
    expected = {
        "provider": "Provider31", "contract": "NQ DEC26", "instrument": "NQ",
        "source_timezone": "UTC", "bar_label": "CLOSE",
        "trading_hours_template": TEMPLATE, "tick_size": .25,
        "point_value": 20, "fixture": False,
    }
    if type(data) is not dict or any(
        type(data.get(key)) is not type(value) or data[key] != value
        for key, value in expected.items()
    ):
        raise ValueError("REVIEWED_NATIVE_FEED_IDENTITY_REQUIRED")
    begin, end = _utc(data.get("valid_from")), _utc(data.get("valid_until"))
    if not begin <= now < end or not timedelta(0) < end - begin <= timedelta(days=14):
        raise ValueError("CURRENT_REVIEWED_CONTRACT_WINDOW_REQUIRED")
    contract = CurrentFeedContractV1(**{
        **data, "provider": "NINJATRADER:" + spec["provider_enum"],
        "valid_from": begin, "valid_until": end,
    })

    first = begin.astimezone(CHICAGO).date() - timedelta(days=1)
    last = end.astimezone(CHICAGO).date() + timedelta(days=1)
    required = []
    day = first
    while day <= last:
        required.append(day)
        day += timedelta(days=1)
    covered = spec.get("covered_dates")
    if (
        type(covered) is not list
        or covered != [day.isoformat() for day in required]
        or spec.get("closed_dates") != []
        or spec.get("special_hours") != []
    ):
        raise ValueError("REVIEWED_ORDINARY_DATE_COVERAGE_REQUIRED")
    affected = set()
    for group in ("HolidaysSerializable", "PartialHolidaysSerializable"):
        node = template.find(group)
        if node is None:
            raise ValueError("REVIEWED_NATIVE_EXCEPTIONS_REQUIRED")
        for row in node:
            exception_day = date.fromisoformat(row.findtext("Date")[:10])
            affected.update(exception_day + timedelta(days=i) for i in (-1, 0, 1))
    if affected.intersection(required):
        raise ValueError("NATIVE_EXCEPTION_MAPPING_REQUIRED")

    hours = CertifiedMarketHoursRuntimeProviderV2(
        calendar_snapshot=CertifiedCalendarSnapshotV2(
            frozenset(required), frozenset(),
        ),
        special_hours_snapshot=CertifiedSpecialHoursSnapshotV2(()),
    )
    gate = CurrentCandleAuthorityV1(
        contract=contract, market_hours=hours,
        maximum_age_seconds=settings.maximum_quote_age_seconds,
        clock=clock,
    )
    entry_authority = None
    l1_reader = None
    if l1_directory is not None:
        base = runtime_binding(reviewed_spec_sha256=reviewed_spec_sha256,
            gate=gate, config=config, state_path=path)
        news = CurrentPaperEconomicNewsAuthorityV1(base=base, clock=clock,
            root=news_root)
        l1_reader = current_paper_l1_reader(settings=settings, gate=gate,
            directory=l1_directory, clock=clock,
            expected_directory_identity=l1_directory_identity)
        entry_authority = CurrentPaperEntryAuthorityV1(gate=gate, news=news,
            l1=l1_reader, settings=settings, clock=clock)
    service = CurrentPaperServiceV1(
        gate=gate, config=config, settings=settings, state_path=path,
        initialization_policy="NEW_ISOLATED_PAPER_ACCOUNT",
        entry_authority=entry_authority,
    )
    service.l1_reader = l1_reader
    if (
        service._runtime is not None
        or service._strategy_bootstrap is not None
        or service._stopped
        or gate.connected
        or gate.fault is not None
        or gate.last_sequence is not None
        or gate.closed_count != 0
    ):
        raise RuntimeError("PAPER_AUTHORITY_NOT_FRESH")
    return service
