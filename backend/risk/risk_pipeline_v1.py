from dataclasses import dataclass

from backend.risk.risk_manager_v2 import (
    RiskManagerV2,
)

from backend.risk.position_sizer_v1 import (
    PositionSizerV1,
)

from backend.risk.account_profile_v1 import (
    AccountProfile,
)



@dataclass
class RiskPipelineResult:

    allowed: bool

    contracts: int

    risk_amount: float

    reason: str



class RiskPipelineV1:
    """
    Pipeline de riesgo ARMS AI.

    Une:

    RiskManagerV2
          +
    PositionSizerV1

    """

    def __init__(
        self,
        *,
        profile: AccountProfile,
    ):

        self.profile = profile


        self.risk_manager = RiskManagerV2(
            account_balance=profile.account_balance,
            risk_percent=profile.risk_percent,
            daily_loss_limit=profile.daily_loss_limit,
        )


        self.position_sizer = PositionSizerV1()



    def evaluate(
        self,
        *,
        entry: float,
        stop_loss: float,
        point_value: float = 20,
        current_loss: float = 0,
    ) -> RiskPipelineResult:


        risk_check = (
            self.risk_manager.validate_trade(
                current_loss=current_loss,
            )
        )


        if not risk_check.allowed:

            return RiskPipelineResult(
                allowed=False,
                contracts=0,
                risk_amount=risk_check.risk_amount,
                reason=risk_check.reason,
            )



        size = (
            self.position_sizer.calculate(
                account_balance=self.profile.account_balance,
                risk_percent=self.profile.risk_percent,
                entry=entry,
                stop_loss=stop_loss,
                point_value=point_value,
            )
        )


        return RiskPipelineResult(
            allowed=True,
            contracts=size.contracts,
            risk_amount=size.risk_amount,
            reason="RISK PIPELINE APPROVED",
        )
