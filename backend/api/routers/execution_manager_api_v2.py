from fastapi import APIRouter

from backend.execution.execution_manager_engine import (
    ExecutionManagerEngine,
)


router = APIRouter(
    prefix="/api/v2/dashboard",
    tags=[
        "Execution Manager"
    ],
)


engine = ExecutionManagerEngine()



@router.get(
    "/execution-manager"
)
def execution_manager_dashboard():

    result = engine.prepare_order(

        symbol="NQ",

        direction="BUY",

        entry=23500,

        stop_loss=23450,

        take_profit=23650,

        contracts=1,

        risk_amount=500,

        approved=True,

    )


    return {

        "status": result.status,

        "symbol": result.symbol,

        "direction": result.direction,

        "order_type": result.order_type,

        "contracts": result.contracts,

        "entry": result.entry,

        "stop_loss": result.stop_loss,

        "take_profit": result.take_profit,

        "risk_amount": result.risk_amount,

        "validation": result.validation,

    }

