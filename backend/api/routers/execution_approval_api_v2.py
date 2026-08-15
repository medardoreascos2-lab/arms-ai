from fastapi import APIRouter

from backend.execution.execution_approval_engine import (
    ExecutionApprovalEngine,
)


router = APIRouter(
    prefix="/api/v2/dashboard",
    tags=[
        "Execution Approval"
    ],
)


execution_engine = ExecutionApprovalEngine()



@router.get(
    "/execution-approval"
)
def execution_approval_dashboard():

    result = execution_engine.validate_execution(

        symbol="NQ",

        direction="BUY",

        entry=23500,

        stop_loss=23450,

        take_profit=23650,

        risk_amount=500,

        confidence=98,

    )


    return {

        "status": result.status,

        "symbol": result.symbol,

        "direction": result.direction,

        "entry": result.entry,

        "stop_loss": result.stop_loss,

        "take_profit": result.take_profit,

        "risk_amount": result.risk_amount,

        "confidence": result.confidence,

        "validation": result.validation,

    }
