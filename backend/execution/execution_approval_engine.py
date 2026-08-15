from dataclasses import dataclass
from typing import List


@dataclass
class ExecutionApproval:

    status: str

    symbol: str

    direction: str

    entry: float

    stop_loss: float

    take_profit: float

    risk_amount: float

    confidence: int

    validation: List[str]



class ExecutionApprovalEngine:


    def __init__(self):
        pass



    def validate_execution(

        self,

        symbol: str,

        direction: str,

        entry: float,

        stop_loss: float,

        take_profit: float,

        risk_amount: float,

        confidence: int,

        daily_loss_used: float = 0,

        daily_loss_limit: float = 3000,

    ) -> ExecutionApproval:


        checks = []


        approved = True



        if confidence >= 80:

            checks.append(
                "AI confidence acceptable"
            )

        else:

            approved = False

            checks.append(
                "AI confidence below minimum"
            )



        if risk_amount > 0:

            checks.append(
                "Risk amount calculated"
            )

        else:

            approved = False

            checks.append(
                "Invalid risk amount"
            )



        if daily_loss_used < daily_loss_limit:

            checks.append(
                "Daily loss limit available"
            )

        else:

            approved = False

            checks.append(
                "Daily loss limit exceeded"
            )



        status = (

            "APPROVED"

            if approved

            else

            "BLOCKED"

        )



        return ExecutionApproval(

            status=status,

            symbol=symbol,

            direction=direction,

            entry=entry,

            stop_loss=stop_loss,

            take_profit=take_profit,

            risk_amount=risk_amount,

            confidence=confidence,

            validation=checks,

        )
