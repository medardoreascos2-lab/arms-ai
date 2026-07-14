from enum import Enum


class PipelineMode(str, Enum):
    """
    Modos de ejecución soportados por ARMS AI.
    """

    SIMULATION = "SIMULATION"
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    LIVE = "LIVE"
