from backend.config_settings import ArmsSettings
from backend.connectors.market_connector import MarketConnector
from backend.core import ArmsCore
from backend.pipeline.arms_pipeline import ArmsPipeline
from backend.pipeline.decision_stage import DecisionStage
from backend.pipeline.execution_stage import ExecutionStage
from backend.pipeline.indicator_stage import IndicatorStage
from backend.pipeline.intelligence_stage import IntelligenceStage
from backend.pipeline.market_stage import MarketStage
from backend.pipeline.reporting_stage import ReportingStage
from backend.pipeline.risk_stage import RiskStage
from backend.pipeline.smart_money_stage import SmartMoneyStage
from backend.pipeline.trade_plan_stage import TradePlanStage
from backend.services.data_collector import DataCollector


def main() -> None:
    settings = ArmsSettings()

    arms = ArmsCore()
    arms.start()

    connector = MarketConnector()
    connector.connect()

    collector = DataCollector(
        provider=settings.provider,
    )

    pipeline = ArmsPipeline(
        stages=[
            MarketStage(
                collector=collector,
                symbol=settings.symbol,
                timeframe=settings.timeframe,
                candle_limit=settings.candle_limit,
                max_candles=settings.max_candles,
            ),
            IndicatorStage(
                ema_period=settings.ema_period,
                rsi_period=settings.rsi_period,
                atr_period=settings.atr_period,
            ),
            SmartMoneyStage(
                liquidity_tolerance=(
                    settings.liquidity_tolerance
                ),
            ),
            IntelligenceStage(),
            RiskStage(
                account_balance=settings.account_balance,
                risk_percent=settings.risk_percent,
                stop_atr_multiplier=(
                    settings.stop_atr_multiplier
                ),
                reward_risk_ratio=(
                    settings.reward_risk_ratio
                ),
                point_value=settings.point_value,
            ),
            DecisionStage(
                reward_risk_ratio=(
                    settings.reward_risk_ratio
                ),
            ),
            TradePlanStage(),
            ExecutionStage(
                trade_log_path=settings.trade_log_path,
                simulated_log_path=(
                    settings.simulated_log_path
                ),
                point_value=settings.point_value,
            ),
            ReportingStage(),
        ]
    )

    pipeline.run(
        initial_context={
            "collector": collector,
            "settings": settings,
        }
    )


if __name__ == "__main__":
    main()
