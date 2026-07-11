from datetime import datetime

from backend.models.candle import Candle
from backend.models.simulated_trade import SimulatedTrade
from backend.models.trade_plan import TradePlan


class ExecutionSimulator:
    def __init__(self, point_value: float = 2.0):
        if point_value <= 0:
            raise ValueError(
                "El valor por punto debe ser mayor que cero."
            )

        self.point_value = point_value

    def execute(
        self,
        trade_plan: TradePlan,
        next_candle: Candle,
    ) -> SimulatedTrade | None:
        if not trade_plan.authorized:
            print("------ EXECUTION SIMULATOR ------")
            print("Operación no ejecutada: plan no autorizado.")
            return None

        if (
            trade_plan.entry_price is None
            or trade_plan.stop_loss is None
            or trade_plan.take_profit is None
        ):
            raise ValueError(
                "El plan no tiene niveles completos de operación."
            )

        opened_at = datetime.now()

        result = "SIN RESULTADO"
        exit_price = next_candle.close

        if trade_plan.decision == "BUSCAR COMPRAS":
            if next_candle.low <= trade_plan.stop_loss:
                result = "STOP LOSS"
                exit_price = trade_plan.stop_loss

            elif next_candle.high >= trade_plan.take_profit:
                result = "TAKE PROFIT"
                exit_price = trade_plan.take_profit

            else:
                result = "CIERRE DE VELA"
                exit_price = next_candle.close

            points = exit_price - trade_plan.entry_price

        elif trade_plan.decision == "BUSCAR VENTAS":
            if next_candle.high >= trade_plan.stop_loss:
                result = "STOP LOSS"
                exit_price = trade_plan.stop_loss

            elif next_candle.low <= trade_plan.take_profit:
                result = "TAKE PROFIT"
                exit_price = trade_plan.take_profit

            else:
                result = "CIERRE DE VELA"
                exit_price = next_candle.close

            points = trade_plan.entry_price - exit_price

        else:
            print("------ EXECUTION SIMULATOR ------")
            print("Operación no ejecutada: decisión ESPERAR.")
            return None

        pnl = (
            points
            * self.point_value
            * trade_plan.contracts
        )

        return SimulatedTrade(
            symbol=trade_plan.symbol,
            timeframe=trade_plan.timeframe,
            direction=trade_plan.decision,
            entry_price=trade_plan.entry_price,
            stop_loss=trade_plan.stop_loss,
            take_profit=trade_plan.take_profit,
            contracts=trade_plan.contracts,
            point_value=self.point_value,
            exit_price=exit_price,
            result=result,
            pnl=pnl,
            opened_at=opened_at,
            closed_at=datetime.now(),
        )