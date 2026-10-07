"""Fail-closed certified native CLOSED-bar handoff into LOCAL PAPER.

This module grants no NinjaTrader account or order authority.  The native
adapter remains the timing/provenance owner; CurrentCandleAuthorityV1 remains
the absolute-time/calendar/OHLCV admission owner; CurrentPaperServiceV1 remains
the isolated SIMULATED / PAPER owner.

PAPER enablement is deliberately outside this bridge.
"""

from collections import deque
from datetime import datetime, timedelta, timezone
from threading import RLock

from backend.backtesting.current_paper_runtime_v1 import (
    CurrentPaperServiceV1,
)
from backend.market_data.certified_bootstrap_v1 import (
    CertifiedBootstrap,
)
from backend.market_data.current_candle_authority_v1 import (
    CurrentMarketEventV1,
    _certify_native_same_callback_closed,
    instant,
)
from backend.market_data.fresh_native_adapter_v1 import (
    FreshNativeAdapterV1,
    MAX_QUEUE,
)
from tools.production_timing_v1 import parse


SCHEMA = "arms.certified-native-paper-bridge.v1"
DELIVERY_SCHEMA = "arms.certified-native-live-closed.v1"
PENDING_CLOSED_LIMIT = MAX_QUEUE


def _utc(value):
    if not isinstance(value, str):
        raise ValueError(
            "BRIDGE_UTC_REQUIRED"
        )

    parsed = datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )

    if (
        parsed.tzinfo is None
        or parsed.utcoffset()
        != timezone.utc.utcoffset(None)
    ):
        raise ValueError(
            "BRIDGE_UTC_REQUIRED"
        )

    return instant(parsed)


class CertifiedNativePaperBridgeV1:
    """One-way data bridge; all financial authority stays in LOCAL PAPER."""

    def __init__(
        self,
        *,
        adapter,
        service,
        wall_clock,
    ):
        if type(adapter) is not FreshNativeAdapterV1:
            raise TypeError(
                "exact FreshNativeAdapterV1 required"
            )

        if type(service) is not CurrentPaperServiceV1:
            raise TypeError(
                "exact CurrentPaperServiceV1 required"
            )

        if not callable(wall_clock):
            raise TypeError(
                "explicit wall clock required"
            )

        if not adapter.live_handoff_enabled:
            raise ValueError(
                "LIVE_HANDOFF_NOT_ENABLED"
            )

        if (
            type(adapter.bootstrap)
            is not CertifiedBootstrap
            or adapter.profile.bootstrap
            is not adapter.bootstrap
        ):
            raise ValueError(
                "CERTIFIED_BOOTSTRAP_REQUIRED"
            )

        self.adapter = adapter
        self.service = service
        self.wall_clock = wall_clock

        # Context-only installation.  CurrentPaperServiceV1 guarantees
        # this creates no runtime/account and performs no strategy call.
        self.service.install_strategy_bootstrap(
            self.adapter.bootstrap
        )

        self.lock = RLock()

        self.status = "WAITING"
        self.reason = None
        self.connected = False
        self.stopped = False

        self.delivery_sequence = 0
        self.delivered_closed = 0
        self.last_source_sequence = None
        self.pending_closed_records = deque()
        self.source_hello = None

    def _metadata(self):
        if (
            self.adapter.hello is None
            or self.adapter.session is None
            or self.adapter.profile.session
            != self.adapter.session
        ):
            raise ValueError(
                "NATIVE_METADATA_UNAVAILABLE"
            )

        row = parse(
            self.adapter.hello
        )

        if (
            row.get("kind") != "HELLO"
            or row.get("session")
            != self.adapter.session
        ):
            raise ValueError(
                "NATIVE_METADATA_UNAVAILABLE"
            )

        payload = row.get(
            "payload"
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "NATIVE_METADATA_UNAVAILABLE"
            )

        contract = (
            self.service.gate.contract
        )

        if not (
            contract.provider
            == (
                "NINJATRADER:"
                + payload.get(
                    "provider",
                    "",
                )
            )
            and contract.contract
            == payload.get("contract")
            and contract.instrument
            == payload.get("instrument")
            == "NQ"
            and contract.tick_size
            == payload.get("tick_size")
            == 0.25
            and contract.point_value
            == payload.get("point_value")
            == 20
            and contract.trading_hours_template
            == payload.get(
                "trading_hours_template"
            )
            and contract.source_timezone
            == payload.get(
                "source_timezone"
            )
            == "UTC"
            and contract.bar_label
            == payload.get("bar_label")
            == "CLOSE"
            and payload.get("timeframe")
            == "1m"
            and payload.get("realtime")
            is True
            and payload.get("read_only")
            is True
            and contract.fixture
            is False
        ):
            raise ValueError(
                "NATIVE_PAPER_CONTRACT_MISMATCH"
            )

        return payload

    def _source_ready(
        self,
        native,
    ):
        return (
            self.adapter.status
            == "LIVE_TAIL"
            and native.get(
                "market_stream"
            )
            == "LIVE"
            and native.get(
                "transport_status"
            )
            == "TRANSPORT_LIVE"
            and native.get(
                "live_handoff_status"
            )
            == "COMPLETE"
            and native.get(
                "timing_pair_status"
            )
            == "EXACT_PREFIX"
            and native.get(
                "fault"
            )
            is None
        )

    def _validated_events(
        self,
        records,
        *,
        now,
    ):
        events = []

        source_sequence = (
            self.last_source_sequence
        )

        delivery_sequence = (
            self.delivery_sequence
        )

        expected_fields = {
            "schema",
            "session",
            "canonical_sequence",
            "event_time",
            "bar_time",
            "source_open",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "handoff",
        }

        for record in records:
            if (
                set(record)
                != expected_fields
                or record["schema"]
                != DELIVERY_SCHEMA
                or record["session"]
                != self.adapter.session
                or record["handoff"]
                != "COMPLETE"
                or type(
                    record[
                        "canonical_sequence"
                    ]
                )
                is not int
                or record[
                    "canonical_sequence"
                ]
                < 0
            ):
                raise ValueError(
                    "INVALID_CERTIFIED_LIVE_DELIVERY"
                )

            canonical_sequence = (
                record[
                    "canonical_sequence"
                ]
            )

            if (
                source_sequence
                is not None
                and canonical_sequence
                <= source_sequence
            ):
                raise ValueError(
                    "NATIVE_DELIVERY_SEQUENCE"
                )

            emitted = _utc(
                record[
                    "event_time"
                ]
            )

            label = _utc(
                record[
                    "bar_time"
                ]
            )

            source_open = _utc(
                record[
                    "source_open"
                ]
            )

            if (
                source_open
                != label
                - timedelta(
                    minutes=1
                )
            ):
                raise ValueError(
                    "NATIVE_CLOSE_LABEL_CONTRACT"
                )

            age = (
                now
                - emitted
            ).total_seconds()

            if not (
                0
                <= age
                <= self.service.gate.maximum_age
            ):
                raise ValueError(
                    "ABSOLUTE_RECENCY_UNPROVEN"
                )

            # The adapter queues this delivery only after the profile has
            # verified the CLOSED -> FORMING same-callback timing pair.
            event = CurrentMarketEventV1(
                provider=(
                    self.service
                    .gate
                    .contract
                    .provider
                ),
                instrument="NQ",
                contract=(
                    self.service
                    .gate
                    .contract
                    .contract
                ),
                kind=(
                    "CLOSED_CANONICAL_CANDLE"
                ),
                event_time=emitted,
                received_at=now,
                bar_time=label,
                sequence=delivery_sequence,
                event_id=(
                    self.adapter.session
                    + ":"
                    + str(
                        canonical_sequence
                    )
                ),
                open=record["open"],
                high=record["high"],
                low=record["low"],
                close=record["close"],
                volume=record["volume"],
            )
            event = _certify_native_same_callback_closed(event)

            events.append(
                (
                    event,
                    canonical_sequence,
                )
            )

            source_sequence = (
                canonical_sequence
            )

            delivery_sequence += 1

        return events

    def _fail(self):
        self.pending_closed_records.clear()
        self.reason = (
            self.reason
            or "CERTIFIED_NATIVE_PAPER_BRIDGE_FAILED"
        )

        self.status = "REVOKED"

        try:
            if self.service.gate.connected:
                self.service.connection(
                    False
                )
        except Exception:
            self.service.gate.connected = False

        try:
            self.service.gate.fail(
                "CERTIFIED_NATIVE_PAPER_BRIDGE_RECOVERY_REQUIRED"
            )
        except (
            ValueError,
            RuntimeError,
        ):
            pass

        raise ValueError(
            self.reason
        )

    def poll(self):
        with self.lock:
            if (
                self.stopped
                or self.reason
                is not None
            ):
                raise RuntimeError(
                    "BRIDGE_STOPPED_OR_REVOKED"
                )

            try:
                native = (
                    self.adapter.snapshot()
                )

                if self.adapter.status in (
                    "REVOKED",
                    "DISCONNECTED",
                ):
                    return self._fail()

                if not self._source_ready(
                    native
                ):
                    if self.pending_closed_records:
                        return self._fail()
                    self.status = "WAITING"

                    return self.get_snapshot(
                        native=native
                    )

                self._metadata()

                if self.source_hello is None:
                    self.source_hello = self.adapter.hello
                elif self.adapter.hello != self.source_hello:
                    raise ValueError(
                        "NATIVE_METADATA_CHANGED"
                    )

                now = instant(
                    self.wall_clock()
                )

                records = (
                    self.adapter
                    .drain_live_closed_records()
                )

                if (
                    len(self.pending_closed_records)
                    + len(records)
                    > PENDING_CLOSED_LIMIT
                ):
                    raise ValueError(
                        "PENDING_CLOSED_QUEUE_LIMIT"
                    )

                self.pending_closed_records.extend(records)

                events = (
                    self._validated_events(
                        self.pending_closed_records,
                        now=now,
                    )
                )

                if not self.connected:
                    gate = self.service.gate

                    if (
                        gate.connected
                        or gate.last_sequence
                        is not None
                        or gate.closed_count
                        != 0
                    ):
                        raise ValueError(
                            "PAPER_SOURCE_ALREADY_OWNED"
                        )

                    self.service.connection(
                        True
                    )

                    self.connected = True

                for (
                    event,
                    source_sequence,
                ) in events:

                    if event.bar_time > now:
                        break

                    self.service.ingest(
                        event
                    )

                    self.pending_closed_records.popleft()
                    self.last_source_sequence = (
                        source_sequence
                    )

                    self.delivery_sequence += 1

                    self.delivered_closed += 1

                self.status = "LIVE"

                return self.get_snapshot(
                    native=native
                )

            except Exception:
                return self._fail()

    def get_snapshot(
        self,
        *,
        native=None,
    ):
        with self.lock:
            paper = (
                self.service
                .get_snapshot()
            )

            return {
                "schema":
                    SCHEMA,
                "status":
                    self.status,
                "reason":
                    self.reason,
                "source_adapter_status":
                    self.adapter.status,
                "source_session":
                    self.adapter.session,
                "source_live_handoff":
                    (
                        None
                        if native is None
                        else native.get(
                            "live_handoff_status"
                        )
                    ),
                "delivered_closed":
                    self.delivered_closed,
                "last_source_sequence":
                    self.last_source_sequence,
                "paper":
                    paper,
                "paper_auto_enable":
                    False,
                "live_execution_allowed":
                    False,
                "ninjatrader_account_access":
                    False,
                "native_order_authority":
                    False,
                "order_submit_reachable":
                    False,
            }

    def close(self):
        with self.lock:
            if self.stopped:
                return

            self.stopped = True
            self.status = "STOPPED"
            self.pending_closed_records.clear()

            try:
                if (
                    self.service.gate.connected
                    and not self.service.gate.fault
                ):
                    self.service.connection(
                        False
                    )
            except Exception:
                pass
