from fastapi import APIRouter

from backend.ai.trading.trade_setup_engine import (
    TradeSetupEngine,
)


router = APIRouter(
    prefix="/api/v2/dashboard",
    tags=[
        "Trade Setup"
    ],
)


@router.get(
    "/trade-setup"
)
def trade_setup_dashboard():

    engine = TradeSetupEngine()


    setup = engine.generate_setup(
        symbol="NQ",
        direction="BUY",
        entry=23500,
        stop_distance=50,
        risk_reward=3,
        quality="A+",
    )


    return {

        "symbol": setup.symbol,

        "direction": setup.direction,

        "entry": setup.entry,

        "stop_loss": setup.stop_loss,

        "take_profit": setup.take_profit,

        "risk_reward": setup.risk_reward,

        "quality": setup.quality,

        "validation": setup.validation,

    }
