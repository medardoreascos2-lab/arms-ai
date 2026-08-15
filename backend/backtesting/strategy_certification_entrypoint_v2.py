from pathlib import Path


class StrategyCertificationEntryPointV2:
    """
    Punto de entrada institucional para certificación.

    Ejecuta BacktestingOrchestratorV2
    utilizando datos históricos reales.
    """

    def __init__(
        self,
        *,
        orchestrator,
    ) -> None:

        if not callable(
            getattr(
                orchestrator,
                "run",
                None,
            )
        ):
            raise TypeError(
                "orchestrator debe implementar run()."
            )

        self.orchestrator = orchestrator


    def run(self):

        csv_path = Path(
            "data/backtest/nq_history_fixed.csv"
        )


        if not csv_path.exists():
            raise FileNotFoundError(
                f"No existe dataset: {csv_path}"
            )


        result = (
            self.orchestrator.run(
                file_path=csv_path,
                output_directory=(
                    "data/certification"
                ),
            )
        )


        return result.certification_result
