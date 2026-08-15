from typing import Any

from backend.smart_money.bos_engine import BOSEngine
from backend.smart_money.choch_engine import CHoCHEngine
from backend.smart_money.liquidity_engine import LiquidityEngine
from backend.smart_money.market_structure import MarketStructureEngine


class SmartMoneyStage:
    """
    Ejecuta los motores de estructura y liquidez de ARMS AI
    usando las velas preparadas por MarketStage.
    """

    def __init__(
        self,
        liquidity_tolerance: float = 1.0,
    ) -> None:
        self.liquidity_tolerance = liquidity_tolerance

    def run(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        if "candles" not in context:
            raise KeyError(
                "SmartMoneyStage requiere 'candles'."
            )

        candles = context["candles"]

        market_structure = MarketStructureEngine()
        market_structure.analyze(candles)

        bos = BOSEngine()
        bos.analyze(candles)

        choch = CHoCHEngine()
        choch.analyze(
            candles=candles,
            market_structure=market_structure.structure,
        )

        liquidity = LiquidityEngine(
            tolerance=self.liquidity_tolerance
        )
        liquidity.analyze(candles)

        context.update(
            {
                "market_structure": market_structure,
                "bos": bos,
                "choch": choch,
                "liquidity": liquidity,
            }
        )

        return context
