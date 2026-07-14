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
    arms = ArmsCore()
    arms.start()

    connector = MarketConnector()
    connector.connect()

    collector = DataCollector(
        provider="SIMULATED",
    )

    pipeline = ArmsPipeline(
        stages=[
            MarketStage(
                collector=collector,
                symbol="NASDAQ / NQ",
                timeframe="1m",
                candle_limit=100,
                max_candles=500,
            ),
            IndicatorStage(
                ema_period=50,
                rsi_period=14,
                atr_period=14,
            ),
            SmartMoneyStage(
                liquidity_tolerance=1.0,
            ),
            IntelligenceStage(),
            RiskStage(
                account_balance=17000,
                risk_percent=0.5,
                stop_atr_multiplier=1.5,
                reward_risk_ratio=2.0,
                point_value=2.0,
            ),
            DecisionStage(
                reward_risk_ratio=2.0,
            ),
            TradePlanStage(),
            ExecutionStage(
                trade_log_path="data/trade_plans.jsonl",
                simulated_log_path="data/simulated_trades.jsonl",
                point_value=2.0,
            ),
            ReportingStage(),
        ]
    )

    pipeline.run(
        initial_context={
            "collector": collector,
        }
    )


if __name__ == "__main__":
    main()
