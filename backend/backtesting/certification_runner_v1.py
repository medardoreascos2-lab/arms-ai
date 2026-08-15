from backend.api.app import create_app
from backend.backtesting.scenario_generator_v1 import (
    ScenarioGeneratorV1,
)
from backend.backtesting.strategy_certification_report_v1 import (
    StrategyCertificationReportV1,
)

from backend.backtesting.strategy_metrics_engine_v1 import (
    StrategyMetricsEngineV1,
)


class CertificationRunnerV1:
    """
    Ejecuta escenarios de certificación
    de la estrategia ARMS AI.
    """

    def __init__(self):

        self.app = create_app()

        self.engine = (
            self.app.state
            .strategy_certification_pipeline_v2
            .orchestrator
            .backtest_engine
        )

        self.generator = (
            ScenarioGeneratorV1()
        )

        self.report = (
            StrategyCertificationReportV1()
        )

        self.metrics = (
            StrategyMetricsEngineV1()
        )


    def run_scenario(
        self,
        name: str,
        candles,
        expected_action: str,
    ):

        context = (
            self.engine.pipeline.run(
                initial_context={
                    "backtest_candles": candles[:-1],
                    "backtest_candle": candles[-2],
                    "backtest_next_candle": candles[-1],
                }
            )
        )

        council = (
            context["council_result"]
        )

        passed = (
            council.action
            == expected_action
        )

        self.report.add_result(
            scenario=name,
            passed=passed,
        )

        self.metrics.add_result(
            scenario=name,
            action=council.action,
            score=context["confluence_result"].score,
            probability=council.probability,
            confidence=council.confidence,
            approved=council.approved,
        )


    def run(self):

        self.run_scenario(
            "Bullish A+",
            self.generator.bullish_a_plus_setup(),
            "BUY",
        )

        self.run_scenario(
            "Bearish A+",
            self.generator.bearish_a_plus_setup(),
            "SELL",
        )

        self.run_scenario(
            "No Trade",
            self.generator.no_trade_setup(),
            "NO_TRADE",
        )

        self.run_scenario(
            "False Breakout",
            self.generator.false_breakout_setup(),
            "NO_TRADE",
        )


        return {
            "report": self.report,
            "metrics": self.metrics,
        }
