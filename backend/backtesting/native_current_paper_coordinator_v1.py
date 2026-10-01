"""Explicit coordinator between certified native analysis and LOCAL PAPER.

The analysis runtime retains ownership of startup, health, adapter polling and
native observation.  The PAPER service retains financial/accounting authority.
This coordinator owns only the opt-in handoff/bridge lifecycle.

No NinjaTrader account, broker or order interface is reachable here.
"""

from threading import RLock

from backend.backtesting.certified_native_paper_bridge_v1 import (
    CertifiedNativePaperBridgeV1,
)
from backend.backtesting.current_paper_runtime_v1 import (
    CurrentPaperServiceV1,
)
from backend.market_data.analysis_startup_v1 import (
    AnalysisStartupV1,
)
from backend.market_data.certified_bootstrap_v1 import (
    CertifiedBootstrap,
)
from backend.market_data.fresh_native_adapter_v1 import (
    FreshNativeAdapterV1,
)


SCHEMA = (
    "arms.native-current-paper-"
    "coordinator.v1"
)


class NativeCurrentPaperCoordinatorV1:
    """Serialize one certified adapter -> bridge -> PAPER lifecycle."""

    def __init__(
        self,
        *,
        analysis_runtime,
        service,
        wall_clock,
        l1_reader=None,
    ):
        if type(analysis_runtime) is not AnalysisStartupV1:
            raise TypeError(
                "exact AnalysisStartupV1 required"
            )

        if type(service) is not CurrentPaperServiceV1:
            raise TypeError(
                "exact CurrentPaperServiceV1 required"
            )

        if not callable(wall_clock):
            raise TypeError(
                "explicit wall clock required"
            )

        self.lock = RLock()

        self.analysis_runtime = analysis_runtime
        self.service = service
        self.wall_clock = wall_clock
        self.l1_reader = l1_reader

        self.adapter = None
        self.bridge = None

        self.status = "ATTACHING"
        self.reason = None
        self.stopped = False
        self.poll_count = 0

        with analysis_runtime.lock:
            adapter = analysis_runtime.adapter
            bootstrap = analysis_runtime.bootstrap

            if (
                analysis_runtime.phase
                != "VERIFYING_WAITING"
                or analysis_runtime.reason
                is not None
                or len(
                    analysis_runtime.observations
                )
                < 3
                or type(adapter)
                is not FreshNativeAdapterV1
                or adapter.status
                != "WAITING"
                or adapter.reason
                is not None
                or adapter.activation_start
                is not None
                or adapter.session
                is not None
                or adapter.market
                is not None
                or adapter.timing
                is not None
                or adapter.queue
                or adapter.pairs
                or adapter.sequence
                != -1
                or adapter.pair_sequence
                != -1
                or adapter.delivered_records
                != 0
                or adapter.live_handoff_enabled
            ):
                raise ValueError(
                    "COORDINATOR_ATTACH_GATE"
                )

            if (
                type(bootstrap)
                is not CertifiedBootstrap
                or not bootstrap.bars
                or adapter.bootstrap
                is not bootstrap
                or adapter.profile.bootstrap
                is not bootstrap
                or analysis_runtime.bootstrap_replacement_count
                != adapter.bootstrap_replacement_count
                or analysis_runtime.bootstrap_replacement_count
                not in (0, 1)
            ):
                raise ValueError(
                    "COORDINATOR_BOOTSTRAP_IDENTITY"
                )

            if (
                service._stopped
                or service._runtime
                is not None
                or service._strategy_bootstrap
                is not None
                or service.gate.connected
                or service.gate.fault
                is not None
                or service.gate.last_sequence
                is not None
                or service.gate.closed_count
                != 0
            ):
                raise ValueError(
                    "COORDINATOR_PAPER_NOT_FRESH"
                )

            adapter.arm_live_handoff()

            try:
                bridge = (
                    CertifiedNativePaperBridgeV1(
                        adapter=adapter,
                        service=service,
                        wall_clock=wall_clock,
                    )
                )
            except BaseException:
                # No half-attached startup may later activate.
                adapter.revoke(
                    "PAPER_COORDINATOR_ATTACH_FAILED"
                )

                service.shutdown()

                raise

            self.adapter = adapter
            self.bridge = bridge
            self.status = (
                "WAITING_FOR_ACTIVATION"
            )

    def _fail(
        self,
        reason,
    ):
        self.reason = (
            self.reason
            or reason
        )

        self.status = "REVOKED"

        try:
            if self.bridge is not None:
                self.bridge.close()
        finally:
            if self.service.gate.fault is None:
                try:
                    self.service.gate.fail(
                        "NATIVE_CURRENT_PAPER_"
                        "COORDINATOR_RECOVERY_REQUIRED"
                    )
                except ValueError:
                    pass

            self.service.shutdown()

        raise RuntimeError(
            self.reason
        )

    def poll(self):
        """Poll only the PAPER bridge; never call AnalysisStartupV1.poll()."""
        with self.lock:
            if (
                self.stopped
                or self.reason
                is not None
            ):
                raise RuntimeError(
                    "COORDINATOR_STOPPED_OR_REVOKED"
                )

            if (
                self.analysis_runtime.adapter
                is not self.adapter
                or self.analysis_runtime.phase
                not in (
                    "VERIFYING_WAITING",
                    "AWAITING_OPERATOR_ACTIVATION",
                )
                or self.analysis_runtime.reason
                is not None
                or self.adapter.reason
                is not None
                or self.adapter.status
                in (
                    "REVOKED",
                    "DISCONNECTED",
                )
            ):
                return self._fail(
                    "ANALYSIS_RUNTIME_UNAVAILABLE"
                )

            try:
                if self.l1_reader is not None:
                    self.l1_reader.poll()
                bridge_snapshot = (
                    self.bridge.poll()
                )
            except Exception:
                return self._fail(
                    "PAPER_BRIDGE_UNAVAILABLE"
                )

            self.poll_count += 1

            if (
                bridge_snapshot.get("status")
                == "LIVE"
            ):
                self.status = "LIVE"
            else:
                self.status = (
                    "WAITING_FOR_LIVE_TAIL"
                )
                self.service.invalidate_health()

            return self.get_snapshot(
                bridge_snapshot=bridge_snapshot
            )

    def get_snapshot(
        self,
        *,
        bridge_snapshot=None,
    ):
        with self.lock:
            if bridge_snapshot is None:
                bridge_snapshot = (
                    self.bridge.get_snapshot()
                    if self.bridge is not None
                    else None
                )

            paper = (
                None
                if bridge_snapshot is None
                else bridge_snapshot.get(
                    "paper"
                )
            )

            return {
                "schema":
                    SCHEMA,
                "status":
                    self.status,
                "reason":
                    self.reason,
                "poll_count":
                    self.poll_count,
                "analysis_run_id":
                    self.analysis_runtime.run_id,
                "analysis_phase":
                    self.analysis_runtime.phase,
                "analysis_runtime_owned":
                    False,
                "analysis_poll_authority":
                    False,
                "source_adapter_status":
                    (
                        None
                        if self.adapter is None
                        else self.adapter.status
                    ),
                "live_handoff_enabled":
                    (
                        False
                        if self.adapter is None
                        else self.adapter.live_handoff_enabled
                    ),
                "bridge":
                    bridge_snapshot,
                "paper":
                    paper,
                "paper_auto_enable":
                    False,
                "paper_control_authority":
                    False,
                "broker_authority":
                    False,
                "ninjatrader_account_access":
                    False,
                "live_execution_allowed":
                    False,
                "native_order_authority":
                    False,
                "order_submit_reachable":
                    False,
            }

    def close(self):
        """Idempotent coordinator shutdown; analysis runtime remains separately owned."""
        with self.lock:
            if self.stopped:
                return

            self.stopped = True

            try:
                if self.bridge is not None:
                    self.bridge.close()
            finally:
                self.service.invalidate_health()
                if self.l1_reader is not None:
                    self.l1_reader.close()
                self.service.shutdown()

            self.status = "STOPPED"
