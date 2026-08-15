from fastapi import APIRouter

from backend.execution.execution_simulator_engine import (
    ExecutionSimulatorEngine,
)


router = APIRouter(
    prefix="/api/v2/dashboard",
    tags=[
        "Execution Simulator"
    ],
)


engine = ExecutionSimulatorEngine()



@router.get(
    "/execution-simulator"
)
def execution_simulator_dashboard():

    result = engine.simulate_execution(

        symbol="NQ",

        direction="BUY",

        entry=23500,

        stop_loss=23450,

        take_profit=23650,

        risk_amount=500,

    )


    return {

        "status": result.status,

        "symbol": result.symbol,

        "direction": result.direction,

        "entry": result.entry,

        "stop_loss": result.stop_loss,

        "take_profit": result.take_profit,

        "risk_points": result.risk_points,

        "reward_points": result.reward_points,

        "risk_reward": result.risk_reward,

        "contracts": result.contracts,

        "max_loss": result.max_loss,

        "expected_profit": result.expected_profit,

    }

