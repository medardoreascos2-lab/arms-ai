from backend.dashboard.risk_dashboard_provider_v1 import (
    RiskDashboardProviderV1,
)


class RiskDashboardAPIv1:
    """
    Adaptador API para datos de riesgo
    del Dashboard ARMS AI.
    """


    def __init__(
        self,
    ):

        self.provider = (
            RiskDashboardProviderV1()
        )



    def get_risk_dashboard(
        self,
    ):

        return (
            self.provider
            .get_risk_status()
        )
