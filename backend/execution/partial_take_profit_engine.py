from __future__ import annotations

from backend.execution.position_manager import (
    PositionManager,
)


class PartialTakeProfitEngine:
    """
    Ejecuta una toma parcial de ganancias
    cuando el precio alcanza el nivel configurado.
    """

    def __init__(
        self,
        *,
        position_manager: PositionManager,
        trigger_points: float,
        contracts_to_close: int,
        point_value: float,
    ) -> None:
        if trigger_points <= 0:
            raise ValueError(
                "trigger_points debe ser mayor que cero."
            )

        if contracts_to_close <= 0:
            raise ValueError(
                "contracts_to_close debe ser mayor que cero."
            )

        if point_value <= 0:
            raise ValueError(
                "point_value debe ser mayor que cero."
            )

        self.position_manager = (
            position_manager
        )
        self.trigger_points = float(
            trigger_points
        )
        self.contracts_to_close = int(
            contracts_to_close
        )
        self.point_value = float(
            point_value
        )

        self._executed_positions: set[
            tuple[str, str, object]
        ] = set()

    def evaluate_price(
        self,
        *,
        symbol: str,
        timeframe: str,
        current_price: float,
    ) -> dict[str, object]:
        position = (
            self.position_manager.get_open_position(
                symbol=symbol,
                timeframe=timeframe,
            )
        )

        if position is None:
            return {
                "status": "NO_POSITION",
                "executed": False,
            }

        key = (
            str(symbol).strip().upper(),
            str(timeframe).strip().lower(),
            position["opened_at"],
        )

        if key in self._executed_positions:
            return {
                "status": "ALREADY_EXECUTED",
                "executed": False,
                "contracts_remaining": (
                    position["contracts"]
                ),
            }

        side = str(
            position["side"]
        ).strip().upper()

        entry_price = float(
            position["entry_price"]
        )

        normalized_price = float(
            current_price
        )

        if side == "LONG":
            trigger_price = (
                entry_price
                + self.trigger_points
            )

            if normalized_price < trigger_price:
                return {
                    "status": "INACTIVE",
                    "executed": False,
                }

        elif side == "SHORT":
            trigger_price = (
                entry_price
                - self.trigger_points
            )

            if normalized_price > trigger_price:
                return {
                    "status": "INACTIVE",
                    "executed": False,
                }

        else:
            raise ValueError(
                "side inválido."
            )

        current_contracts = int(
            position["contracts"]
        )

        if (
            self.contracts_to_close
            >= current_contracts
        ):
            return {
                "status": (
                    "INSUFFICIENT_CONTRACTS"
                ),
                "executed": False,
                "contracts_available": (
                    current_contracts
                ),
                "contracts_to_close": (
                    self.contracts_to_close
                ),
                "contracts_remaining": (
                    current_contracts
                ),
            }

        reduction = (
            self.position_manager.reduce_position(
                symbol=symbol,
                timeframe=timeframe,
                contracts_to_close=(
                    self.contracts_to_close
                ),
                exit_price=normalized_price,
                point_value=self.point_value,
            )
        )

        self._executed_positions.add(
            key
        )

        return {
            **reduction,
            "status": "PARTIAL_TAKE_PROFIT",
            "executed": True,
        }
