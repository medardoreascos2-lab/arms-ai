from backend.models.decision_council_result import DecisionCouncilResult
from backend.models.trade_plan import TradePlan


class TradePlanFactory:
    """
    Convierte el resultado unificado del Decision Council
    en un TradePlan compatible con el resto del sistema.

    Regla de seguridad:
    si el Council no aprueba la operación, el plan se crea
    sin contratos ni niveles ejecutables.
    """

    def create(
        self,
        symbol: str,
        timeframe: str,
        council_result: DecisionCouncilResult,
        entry_price: float | None,
        stop_loss: float | None,
        take_profit: float | None,
        contracts: int,
        risk_amount: float,
    ) -> TradePlan:
        reasons = self._build_reasons(council_result)

        if not council_result.approved:
            return TradePlan(
                symbol=symbol,
                timeframe=timeframe,
                decision="NO_TRADE",
                confidence=council_result.confidence,
                entry_price=None,
                stop_loss=None,
                take_profit=None,
                contracts=0,
                risk_amount=0.0,
                authorized=False,
                reasons=reasons,
            )

        return TradePlan(
            symbol=symbol,
            timeframe=timeframe,
            decision=council_result.action,
            confidence=council_result.confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            contracts=contracts,
            risk_amount=risk_amount,
            authorized=True,
            reasons=reasons,
        )

    def _build_reasons(
        self,
        council_result: DecisionCouncilResult,
    ) -> list[str]:
        reasons: list[str] = []

        for item in (
            council_result.reasons
            + council_result.blockers
            + council_result.warnings
        ):
            if item and item not in reasons:
                reasons.append(item)

        return reasons
