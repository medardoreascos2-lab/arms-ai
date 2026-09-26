from __future__ import annotations

from copy import deepcopy

from backend.backtesting.paper_runtime_v1 import (
    _encode,
)
from backend.backtesting.operational_paper_v1 import (
    OperationalPaperV1,
)


class PaperSessionCloseServiceV2:
    def __init__(
        self,
        *,
        operational_paper: OperationalPaperV1,
    ) -> None:
        if not isinstance(
            operational_paper,
            OperationalPaperV1,
        ):
            raise TypeError(
                "operational_paper debe ser OperationalPaperV1."
            )

        self.operational_paper = (
            operational_paper
        )

        self._last_close_report: (
            dict[str, object] | None
        ) = None

    def _latch_recovery(
        self,
        *,
        runtime,
        exc: Exception,
    ) -> None:
        op = self.operational_paper

        op.enabled = False
        op.fault = (
            "SESSION_CLOSE_RECOVERY_REQUIRED"
        )

        if (
            runtime is not None
            and not runtime._stopped
        ):
            runtime._fault = (
                "RECOVERY_REQUIRED"
            )
            runtime._fault_detail = (
                type(exc).__name__
                + ": "
                + str(exc)
            )

            try:
                runtime._publish()
                runtime._save()
            except Exception:
                pass


    def close_session(
        self,
        *,
        prices_by_symbol: dict[str, float],
        policy: str = "FLAT",
    ) -> dict[str, object]:
        op = self.operational_paper

        normalized_policy = (
            str(policy)
            .strip()
            .upper()
        )

        if normalized_policy != "FLAT":
            raise ValueError(
                "solo policy FLAT está soportada."
            )

        if not isinstance(
            prices_by_symbol,
            dict,
        ):
            raise TypeError(
                "prices_by_symbol debe ser un dict."
            )

        if op.stopped:
            if self._last_close_report is not None:
                return deepcopy(
                    self._last_close_report
                )

            raise RuntimeError(
                "SESSION_ALREADY_STOPPED"
            )

        if op.runtime is None:
            op.enabled = False
            op.close()

            return {
                "success": True,
                "status": "SESSION_CLOSED",
                "policy": "FLAT",
                "closed_positions": 0,
                "remaining_positions": 0,
                "reconciliation": {
                    "duplicate_execution": 0,
                    "duplicate_pnl": 0,
                    "account_drift": 0,
                    "journal_mismatch": 0,
                    "unexplained_differences": 0,
                },
            }

        runtime = op.runtime
        accounting = runtime._paper.runtime
        lifecycle = accounting.lifecycle

        # Block new entries before any close mutation.
        op.enabled = False
        runtime.control("disable")

        active_positions = [
            dict(position)
            for position
            in lifecycle.get_active_positions()
        ]

        normalized_prices: dict[str, float] = {}

        # Validate every price before closing anything.
        for position in active_positions:
            symbol = (
                str(
                    position.get(
                        "symbol",
                        "",
                    )
                )
                .strip()
                .upper()
            )

            if not symbol:
                exc = ValueError(
                    "active position without symbol"
                )
                self._latch_recovery(
                    runtime=runtime,
                    exc=exc,
                )
                raise exc

            if symbol not in prices_by_symbol:
                exc = ValueError(
                    f"missing session close price for {symbol}"
                )
                self._latch_recovery(
                    runtime=runtime,
                    exc=exc,
                )
                raise exc

            price = float(
                prices_by_symbol[symbol]
            )

            if price <= 0:
                exc = ValueError(
                    f"invalid session close price for {symbol}"
                )
                self._latch_recovery(
                    runtime=runtime,
                    exc=exc,
                )
                raise exc

            normalized_prices[symbol] = price

        closed_positions = []

        try:
            for position in active_positions:
                symbol = str(
                    position["symbol"]
                ).strip().upper()

                result = (
                    lifecycle.close_active_position(
                        position_id=(
                            position["position_id"]
                        ),
                        current_price=(
                            normalized_prices[symbol]
                        ),
                        reason="SESSION_CLOSE",
                    )
                )

                closed = dict(
                    result["position"]
                )

                accounting.record_close(
                    closed
                )

                runtime._db.execute(
                    "INSERT INTO journal VALUES(?,?)",
                    (
                        closed["position_id"],
                        _encode(
                            accounting.completed[-1]
                        ),
                    ),
                )

                closed_positions.append(
                    closed
                )

            if lifecycle.get_active_positions():
                raise RuntimeError(
                    "SESSION_CLOSE_NOT_FLAT"
                )

            if accounting.portfolio.get_open_positions():
                raise RuntimeError(
                    "SESSION_CLOSE_PORTFOLIO_NOT_FLAT"
                )

            runtime._publish()

            reconciliation = (
                op.reconcile()
            )

            if any(
                reconciliation.values()
            ):
                raise RuntimeError(
                    "PAPER_RECONCILIATION_FAILED"
                )

            runtime._save()

            op.close()

            report = {
                "success": True,
                "status": "SESSION_CLOSED",
                "policy": normalized_policy,
                "closed_positions": len(
                    closed_positions
                ),
                "remaining_positions": 0,
                "reconciliation": deepcopy(
                    reconciliation
                ),
            }

            self._last_close_report = deepcopy(
                report
            )

            return report

        except Exception as exc:
            self._latch_recovery(
                runtime=runtime,
                exc=exc,
            )
            raise
