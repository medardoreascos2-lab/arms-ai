from __future__ import annotations

from backend.execution.position_sizing_engine_v2 import (
    PositionSizingEngineV2,
)
from backend.execution.risk_manager_v2 import (
    RiskManagerV2,
)
from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)
from backend.risk.risk_compatibility_adapter_v2 import (
    RiskCompatibilityAdapterV2,
)


class BacktestRiskAdapterFactoryV2:
    """
    Construye el adaptador moderno de riesgo utilizado por
    BacktestSessionV2.

    La configuración de cuenta continúa siendo obtenida desde
    AccountConfigManagerV2, y la evaluación real de riesgo
    utiliza:

        RiskManagerV2
              +
        PositionSizingEngineV2
              +
        RiskCompatibilityAdapterV2

    No contiene lógica de decisión de riesgo.
    """

    @staticmethod
    def create(
        *,
        account_config: AccountConfigManagerV2 | None = None,
        maximum_contracts: int = 20,
        maximum_open_positions: int = 1,
    ) -> RiskCompatibilityAdapterV2:
        config = (
            account_config
            if account_config is not None
            else AccountConfigManagerV2()
        )

        profile = config.get_active_account()

        if maximum_contracts <= 0:
            raise ValueError(
                "maximum_contracts debe ser mayor que cero."
            )

        if maximum_open_positions <= 0:
            raise ValueError(
                "maximum_open_positions debe ser mayor que cero."
            )

        manager = RiskManagerV2(
            position_sizing_engine=PositionSizingEngineV2(),
            maximum_daily_loss=(
                profile.daily_loss_limit
            ),
            maximum_total_drawdown=(
                profile.max_drawdown
            ),
            maximum_contracts=maximum_contracts,
            maximum_open_positions=maximum_open_positions,
        )

        return RiskCompatibilityAdapterV2(
            risk_manager=manager,
        )
